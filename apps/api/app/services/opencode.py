"""Local-only isolated OpenCode runner for API-key-based RAG requests."""

import json
import secrets
import subprocess
import time
from pathlib import Path
from threading import BoundedSemaphore

from app.core.errors import APIError

WORKER_DIR = Path(__file__).resolve().parents[1] / "opencode_worker"
SLOTS = BoundedSemaphore(2)


def worker_access(settings, client_host, *, chatgpt):
    """Raise unless an OpenCode worker for this credential kind may serve the client."""
    if chatgpt:
        hosted = settings.opencode_chatgpt_hosted_enabled
        enabled = hosted or settings.opencode_chatgpt_local_enabled
    else:
        hosted = settings.opencode_api_keys_hosted_enabled
        enabled = hosted or settings.opencode_local_enabled
    if not enabled:
        raise APIError(503, "opencode_unavailable", "OpenCode worker is not enabled")
    if (
        not hosted
        and settings.app_env.lower() != "test"
        and client_host not in {"127.0.0.1", "::1"}
    ):
        raise APIError(403, "forbidden", "OpenCode worker is available only locally")


class OpenCodeService:
    def __init__(self, settings, api_key, model, provider="openai"):
        self.settings = settings
        self.api_key = api_key
        if provider not in {"openai", "anthropic", "deepseek", "openrouter"}:
            raise ValueError("Unsupported provider")
        self.provider = provider
        self.model = model or settings.default_llm_model

    def answer(self, question, chunks):
        if not SLOTS.acquire(blocking=False):
            raise APIError(429, "ai_rate_limited", "OpenCode is busy; retry later")
        name = "legal-opencode-" + secrets.token_hex(8)
        guard = name + "-guard"
        worker = name + "-worker"
        secret = secrets.token_urlsafe(32)
        binary = Path(self.settings.opencode_binary).resolve()
        image = self.settings.opencode_image
        guard_script = WORKER_DIR / "guard.py"
        worker_script = WORKER_DIR / "worker.py"
        deadline = time.monotonic() + 75

        def docker(args, *, cleanup=False, **kwargs):
            timeout = kwargs.pop("timeout", 15)
            if not cleanup:
                timeout = min(timeout, max(0.01, deadline - time.monotonic()))
            return subprocess.run(
                ["docker", *args],
                check=True,
                capture_output=True,
                timeout=timeout,
                **kwargs,
            )

        try:
            if not binary.is_file() or not guard_script.is_file() or not worker_script.is_file():
                raise APIError(503, "ai_unavailable", "OpenCode local worker is not configured")
            docker(["network", "create", "--internal", name])
            docker(
                [
                    "run",
                    "-d",
                    "--rm",
                    "--name",
                    guard,
                    "--network",
                    name,
                    "--network-alias",
                    "guard",
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
                    "64",
                    "--memory",
                    "128m",
                    "--cpus",
                    "0.5",
                    "--tmpfs",
                    "/tmp:rw,nosuid,size=16m",
                    "-e",
                    "OPENCODE_GUARD_SECRET=" + secret,
                    "-e",
                    "OPENCODE_GUARD_PROVIDER=" + self.provider,
                    "-e",
                    "OPENCODE_MAX_OUTPUT_TOKENS=" + str(self.settings.ai_max_output_tokens),
                    "--mount",
                    f"type=bind,src={guard_script},dst=/opt/guard.py,readonly",
                    "--entrypoint",
                    "python",
                    image,
                    "/opt/guard.py",
                ]
            )
            docker(["network", "connect", "bridge", guard])
            context = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, 1))
            job = {
                "apiKey": self.api_key,
                "provider": self.provider,
                "model": self.model,
                "guardSecret": secret,
                "serverSecret": secrets.token_urlsafe(32),
                "prompt": f"Câu hỏi: {question}\n\nNguồn:\n{context}",
            }
            result = docker(
                [
                    "run",
                    "--rm",
                    "-i",
                    "--name",
                    worker,
                    "--network",
                    name,
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
                    "--tmpfs",
                    "/app:rw,nosuid,size=8m",
                    "--mount",
                    f"type=bind,src={binary},dst=/usr/local/bin/opencode,readonly",
                    "--mount",
                    f"type=bind,src={worker_script},dst=/opt/worker.py,readonly",
                    "--entrypoint",
                    "python",
                    image,
                    "/opt/worker.py",
                ],
                input=json.dumps(job).encode(),
                timeout=115,
            )
            payload = json.loads(result.stdout)
            error = payload.get("error")
            if error == "ai_authentication_failed":
                raise APIError(502, error, "The AI provider rejected the selected key")
            if error == "ai_rate_limited":
                raise APIError(429, error, "The AI provider usage limit was reached")
            if error == "ai_incomplete":
                raise APIError(502, error, "The AI response did not finish")
            answer = payload.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("empty answer")
            return answer
        except APIError:
            raise
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            raise APIError(
                503, "ai_unavailable", "OpenCode local worker could not complete the request"
            ) from None
        finally:
            try:
                docker(["rm", "-f", worker], timeout=10, cleanup=True)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                docker(["rm", "-f", guard], timeout=10, cleanup=True)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                docker(["network", "rm", name], timeout=10, cleanup=True)
            except (OSError, subprocess.SubprocessError):
                pass
            SLOTS.release()
