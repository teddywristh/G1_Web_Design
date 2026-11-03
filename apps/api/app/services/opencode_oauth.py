"""Isolated OpenCode workers with encrypted per-user OAuth recovery."""

import json
import secrets
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from app.core.errors import APIError
from app.services import oauth_store

WORKER_DIR = Path(__file__).resolve().parents[1] / "opencode_worker"
SESSIONS = {}
LOCK = threading.RLock()
RESTORE_LOCK = threading.RLock()


def docker(args, **kwargs):
    return subprocess.run(["docker", *args], check=True, capture_output=True, **kwargs)


def cleanup(session):
    for name in (session["worker"], session["guard"]):
        try:
            docker(["rm", "-f", name], timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        docker(["network", "rm", session["network"]], timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def expire():
    now = time.monotonic()
    with LOCK:
        expired = [
            key
            for key, session in SESSIONS.items()
            if now >= session["expires"] and not (session.get("lock") and session["lock"].locked())
        ]
        sessions = [SESSIONS.pop(key) for key in expired]
    for session in sessions:
        cleanup(session)


def invoke(session, payload, timeout):
    try:
        result = docker(
            ["exec", "-i", session["worker"], "python", "/opt/oauth_call.py"],
            input=json.dumps(payload).encode(),
            timeout=timeout,
        )
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (OSError, ValueError, subprocess.SubprocessError):
        try:
            running = (
                docker(
                    ["inspect", "-f", "{{.State.Running}}", session["worker"]], timeout=5
                ).stdout.strip()
                == b"true"
            )
        except (OSError, subprocess.SubprocessError):
            running = False
        if not running:
            with LOCK:
                for key, value in list(SESSIONS.items()):
                    if value is session:
                        SESSIONS.pop(key, None)
            cleanup(session)
            raise APIError(
                409, "chatgpt_disconnected", "ChatGPT worker stopped; reconnect to continue"
            ) from None
        raise APIError(503, "opencode_unavailable", "OpenCode OAuth worker failed") from None


def start(user_id, settings, credential=None):
    expire()
    binary = Path(settings.opencode_binary).resolve()
    if not binary.is_file():
        raise APIError(503, "opencode_unavailable", "OpenCode is not configured")
    name = "legal-oauth-" + secrets.token_hex(8)
    session = {
        "worker": name + "-worker",
        "guard": name + "-guard",
        "network": name,
        "expires": time.monotonic() + 3300,
        "connected": False,
        "lock": threading.Lock(),
    }
    with LOCK:
        if user_id in SESSIONS:
            raise APIError(409, "oauth_exists", "Disconnect the current ChatGPT session first")
        if len(SESSIONS) >= 2:
            raise APIError(429, "ai_rate_limited", "OpenCode is busy; retry later")
        SESSIONS[user_id] = session
    image = settings.opencode_image
    try:
        docker(["network", "create", "--internal", name], timeout=15)
        common = [
            "--user",
            "10001:10001",
            "--read-only",
            "--log-driver",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "80",
            "--memory",
            "1024m",
            "--cpus",
            "1",
            "--tmpfs",
            "/tmp:rw,nosuid,size=128m",
        ]
        models = Path(settings.opencode_models_file).expanduser()
        model_mount = (
            ["--mount", f"type=bind,src={models.resolve()},dst=/opt/models.json,readonly"]
            if models.is_file()
            else []
        )
        docker(
            [
                "run",
                "-d",
                "--rm",
                "--name",
                session["guard"],
                "--network",
                name,
                "--network-alias",
                "guard",
                *common,
                "--mount",
                f"type=bind,src={WORKER_DIR / 'oauth_guard.py'},dst=/opt/oauth_guard.py,readonly",
                "--entrypoint",
                "python",
                image,
                "/opt/oauth_guard.py",
            ],
            timeout=20,
        )
        docker(["network", "connect", "bridge", session["guard"]], timeout=15)
        docker(
            [
                "run",
                "-d",
                "--rm",
                "--name",
                session["worker"],
                "--network",
                name,
                *common,
                "--tmpfs",
                "/app:rw,nosuid,size=8m",
                *model_mount,
                "-e",
                "OPENCODE_SERVER_PASSWORD=" + secrets.token_urlsafe(32),
                "--mount",
                f"type=bind,src={binary},dst=/usr/local/bin/opencode,readonly",
                "--mount",
                f"type=bind,src={WORKER_DIR / 'oauth_server.py'},dst=/opt/oauth_server.py,readonly",
                "--mount",
                f"type=bind,src={WORKER_DIR / 'oauth_call.py'},dst=/opt/oauth_call.py,readonly",
                "--entrypoint",
                "python",
                image,
                "/opt/oauth_server.py",
            ],
            timeout=20,
        )
        if credential is not None:
            result = invoke(session, {"action": "restore", "credential": credential}, 90)
            if not result.get("restored"):
                raise ValueError("OAuth restore failed")
            session["connected"] = True
            return {"connected": True}
        result = invoke(session, {"action": "start"}, 90)
        url = result.get("url", "")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "auth.openai.com"
            or parsed.username
            or parsed.password
        ):
            raise ValueError("unexpected OAuth URL")
        instructions = result.get("instructions")
        if not isinstance(instructions, str) or len(instructions) > 2000:
            raise ValueError("unexpected instructions")
        return {"url": url, "instructions": instructions, "connected": False}
    except Exception:
        with LOCK:
            if SESSIONS.get(user_id) is session:
                SESSIONS.pop(user_id)
        cleanup(session)
        raise APIError(503, "opencode_unavailable", "Could not start ChatGPT sign-in") from None


def get(user_id, repo=None, settings=None, _restored=False):
    expire()
    with LOCK:
        session = SESSIONS.get(user_id)
    if not session:
        if repo is None or settings is None:
            return None
        with RESTORE_LOCK:
            with LOCK:
                session = SESSIONS.get(user_id)
            if not session:
                credential = oauth_store.load(repo, settings, user_id)
                if credential is None:
                    return None
                start(user_id, settings, credential=credential)
                _restored = True
                with LOCK:
                    session = SESSIONS.get(user_id)
    try:
        running = (
            docker(
                ["inspect", "-f", "{{.State.Running}}", session["worker"]], timeout=5
            ).stdout.strip()
            == b"true"
        )
    except (OSError, subprocess.SubprocessError):
        running = False
    if running:
        return session
    with LOCK:
        if SESSIONS.get(user_id) is session:
            SESSIONS.pop(user_id, None)
    cleanup(session)
    if repo is not None and settings is not None and not _restored:
        return get(user_id, repo, settings, _restored=True)
    if _restored:
        raise APIError(503, "opencode_unavailable", "Could not restore ChatGPT worker")
    return None


def finish(user_id, repo=None, settings=None):
    session = get(user_id)
    if not session:
        raise APIError(404, "oauth_not_started", "Start ChatGPT sign-in first")
    with session["lock"]:
        data = invoke(session, {"action": "finish"}, 250)
        if not data.get("connected"):
            raise APIError(503, "ai_authentication_failed", "ChatGPT sign-in was not completed")
        if repo is not None and settings is not None:
            credential = invoke(session, {"action": "export"}, 15).get("credential")
            oauth_store.save(repo, settings, user_id, credential)
        session["connected"] = True
    return {"connected": True}


def disconnect(user_id, repo=None):
    # Serialize disconnect with restore and in-flight token refresh/save.
    with RESTORE_LOCK:
        with LOCK:
            session = SESSIONS.get(user_id)
        if session:
            with session["lock"]:
                if repo is not None:
                    oauth_store.remove(repo, user_id)
                with LOCK:
                    if SESSIONS.get(user_id) is session:
                        SESSIONS.pop(user_id, None)
        elif repo is not None:
            oauth_store.remove(repo, user_id)
    if session:
        cleanup(session)


class OAuthAnswer:
    def __init__(self, user_id, model, repo=None, settings=None):
        self.user_id = user_id
        self.model = model or "gpt-5.6-luna"
        self.repo = repo
        self.settings = settings

    def require_session(self):
        session = get(self.user_id, self.repo, self.settings) if self.repo else get(self.user_id)
        if not session or not session["connected"]:
            raise APIError(409, "chatgpt_disconnected", "Reconnect ChatGPT in AI connections")
        return session

    def answer(self, question, chunks):
        session = self.require_session()
        context = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, 1))
        with session["lock"]:
            try:
                data = invoke(
                    session,
                    {
                        "action": "answer",
                        "model": self.model,
                        "prompt": f"Câu hỏi: {question}\n\nNguồn:\n{context}",
                    },
                    90,
                )
            except APIError:
                # A provider error can occur after a successful token rotation.
                # Persist the latest credential if the worker is still alive.
                if self.repo is not None and self.settings is not None:
                    with LOCK:
                        still_active = SESSIONS.get(self.user_id) is session
                    if still_active:
                        try:
                            credential = invoke(session, {"action": "export"}, 15).get("credential")
                            oauth_store.save(self.repo, self.settings, self.user_id, credential)
                        except APIError:
                            pass
                raise
            if self.repo is not None and self.settings is not None:
                credential = invoke(session, {"action": "export"}, 15).get("credential")
                oauth_store.save(self.repo, self.settings, self.user_id, credential)
        error = data.get("error")
        if error:
            raise APIError(
                429 if error == "ai_rate_limited" else 502, error, "ChatGPT request failed"
            )
        answer = data.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise APIError(502, "ai_incomplete", "ChatGPT returned an incomplete response")
        return answer
