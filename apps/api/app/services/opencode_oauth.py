"""Isolated OpenCode workers with encrypted per-user OAuth recovery."""

import hashlib
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
EFFORTS = {"none", "minimal", "low", "medium", "high"}
SESSION_CHECK_SECONDS = 30
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


def worker_failed(session):
    """Translate a failed worker call: a stopped worker means the connection is gone."""
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
        raise APIError(409, "chatgpt_disconnected", "ChatGPT worker stopped; reconnect to continue")
    raise APIError(503, "opencode_unavailable", "OpenCode OAuth worker failed")


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
        worker_failed(session)


def invoke_stream(session, payload, timeout):
    """Like invoke(), but yields each JSON line the worker prints as soon as it is printed."""
    proc = None
    failed = False
    try:
        proc = subprocess.Popen(
            ["docker", "exec", "-i", session["worker"], "python", "/opt/oauth_call.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        watchdog = threading.Timer(timeout, proc.kill)
        watchdog.start()
        try:
            proc.stdin.write(json.dumps(payload).encode())
            proc.stdin.close()
            for raw in proc.stdout:
                line = json.loads(raw)
                if not isinstance(line, dict):
                    raise ValueError()
                yield line
        finally:
            watchdog.cancel()
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        failed = proc.returncode != 0
    except (OSError, ValueError, subprocess.SubprocessError):
        failed = True
    if failed:
        worker_failed(session)


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
        # Registered before its containers exist; other requests must not judge it until then.
        "starting": True,
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
            session["starting"] = False
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
        session["starting"] = False
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
    if (
        session is not None
        and session.get("starting")
        and repo is not None
        and settings is not None
    ):
        # Another request is restoring this session right now. Without this wait, the first page
        # load (which asks for the models and the ChatGPT status at once) would find a worker that
        # is still starting, take it for dead, tear it down and crash on the session it lost.
        with RESTORE_LOCK:
            pass
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
    if session is None:  # removed again while it was being restored
        return None
    if session.get("starting"):
        return session  # being started by another request; not ours to judge
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


def models(user_id, repo=None, settings=None):
    session = get(user_id, repo, settings)
    if not session or not session["connected"]:
        raise APIError(409, "chatgpt_disconnected", "Reconnect ChatGPT in AI connections")
    data = invoke(session, {"action": "models"}, 30).get("models")
    if not isinstance(data, list):
        raise APIError(503, "opencode_unavailable", "OpenCode returned no model list")
    return data


class OAuthAnswer:
    def __init__(self, user_id, model, repo=None, settings=None):
        self.user_id = user_id
        self.model = model or "gpt-5.6-luna"
        self.repo = repo
        self.settings = settings
        self._session = None
        self._checked = 0.0

    def require_session(self):
        session = get(self.user_id, self.repo, self.settings) if self.repo else get(self.user_id)
        if not session or not session["connected"]:
            raise APIError(409, "chatgpt_disconnected", "Reconnect ChatGPT in AI connections")
        self._session, self._checked = session, time.monotonic()
        return session

    def current_session(self):
        """The worker was checked a moment ago for this very request; do not ask Docker again."""
        if self._session is not None and time.monotonic() - self._checked < SESSION_CHECK_SECONDS:
            return self._session
        return self.require_session()

    def payload(self, question, chunks, effort, stream):
        context = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, 1))
        payload = {
            "action": "answer",
            "model": self.model,
            "prompt": f"Câu hỏi: {question}\n\nNguồn:\n{context}",
        }
        if effort in EFFORTS:
            payload["variant"] = effort
        if stream:
            payload["stream"] = True
        return payload

    def persist(self, session, data=None):
        """Save the OAuth credential if the provider rotated it; unchanged ones cost no write."""
        if self.repo is None or self.settings is None:
            return
        credential = (data or {}).get("credential")
        if credential is None:  # a worker started before the combined call: ask for it
            credential = invoke(session, {"action": "export"}, 15).get("credential")
        if credential is None:
            return
        digest = hashlib.sha256(json.dumps(credential, sort_keys=True).encode()).hexdigest()
        if session.get("saved") == digest:
            return
        oauth_store.save(self.repo, self.settings, self.user_id, credential)
        session["saved"] = digest

    def settle(self, session, data):
        """Persist the credential after a call. A saving problem must not hide a provider error."""
        if not data.get("error"):
            self.persist(session, data)
            return
        try:
            self.persist(session, data)
        except APIError:
            pass

    def persist_after_failure(self, session):
        # A provider error can occur after a successful token rotation.
        # Persist the latest credential if the worker is still alive.
        if self.repo is not None and self.settings is not None:
            with LOCK:
                still_active = SESSIONS.get(self.user_id) is session
            if still_active:
                try:
                    self.persist(session)
                except APIError:
                    pass

    @staticmethod
    def text_of(data):
        error = data.get("error")
        if error:
            raise APIError(
                429 if error == "ai_rate_limited" else 502, error, "ChatGPT request failed"
            )
        answer = data.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise APIError(502, "ai_incomplete", "ChatGPT returned an incomplete response")
        return answer

    def answer(self, question, chunks, effort=None):
        session = self.current_session()
        with session["lock"]:
            try:
                data = invoke(session, self.payload(question, chunks, effort, False), 90)
            except APIError:
                self.persist_after_failure(session)
                raise
            self.settle(session, data)
        return self.text_of(data)

    def answer_stream(self, question, chunks, effort=None):
        """Yield text as the model writes it; raises the same safe errors as answer()."""
        session = self.current_session()
        with session["lock"]:
            sent, final = "", None
            try:
                for line in invoke_stream(
                    session, self.payload(question, chunks, effort, True), 90
                ):
                    if isinstance(line.get("delta"), str):
                        sent += line["delta"]
                        yield line["delta"]
                    else:
                        final = line
            except APIError:
                self.persist_after_failure(session)
                raise
            if final is None:
                raise APIError(503, "opencode_unavailable", "OpenCode OAuth worker failed")
            self.settle(session, final)
        text = self.text_of(final)
        if text.startswith(sent) and len(text) > len(sent):
            yield text[len(sent) :]
