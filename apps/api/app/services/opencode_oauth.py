"""Local-only, ephemeral OpenCode OAuth sessions, isolated per application user."""

import json
import secrets
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from app.core.errors import APIError

WORKER_DIR = Path(__file__).resolve().parents[1] / "opencode_worker"
SESSIONS = {}
LOCK = threading.RLock()


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
        expired = [key for key, session in SESSIONS.items() if now >= session["expires"]]
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
        raise APIError(503, "opencode_unavailable", "OpenCode OAuth worker failed") from None


def start(user_id, settings):
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
            "512m",
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


def get(user_id):
    expire()
    with LOCK:
        return SESSIONS.get(user_id)


def finish(user_id):
    session = get(user_id)
    if not session:
        raise APIError(404, "oauth_not_started", "Start ChatGPT sign-in first")
    with session["lock"]:
        data = invoke(session, {"action": "finish"}, 250)
        if not data.get("connected"):
            raise APIError(503, "ai_authentication_failed", "ChatGPT sign-in was not completed")
        session["connected"] = True
    return {"connected": True}


def disconnect(user_id):
    with LOCK:
        session = SESSIONS.pop(user_id, None)
    if session:
        cleanup(session)


class OAuthAnswer:
    def __init__(self, user_id, model):
        self.user_id = user_id
        self.model = model or "gpt-5.6-luna"

    def answer(self, question, chunks):
        session = get(self.user_id)
        if not session or not session["connected"]:
            raise APIError(503, "ai_not_configured", "Connect ChatGPT first")
        context = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, 1))
        with session["lock"]:
            data = invoke(
                session,
                {
                    "action": "answer",
                    "model": self.model,
                    "prompt": f"Câu hỏi: {question}\n\nNguồn:\n{context}",
                },
                90,
            )
        error = data.get("error")
        if error:
            raise APIError(
                429 if error == "ai_rate_limited" else 502, error, "ChatGPT request failed"
            )
        answer = data.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise APIError(502, "ai_incomplete", "ChatGPT returned an incomplete response")
        return answer
