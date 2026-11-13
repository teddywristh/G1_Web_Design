"""Local-only isolated OpenCode runner for API-key-based RAG requests."""

import json
import secrets
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from threading import BoundedSemaphore
from types import SimpleNamespace

from app.core.errors import APIError

WORKER_DIR = Path(__file__).resolve().parents[1] / "opencode_worker"
SLOTS = BoundedSemaphore(2)
EFFORTS = {"none", "minimal", "low", "medium", "high"}


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


def worker_answer(payload):
    """The text of a worker's final line, or the safe API error it reports."""
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


class OpenCodeService:
    def __init__(self, settings, api_key, model, provider="openai"):
        self.settings = settings
        self.api_key = api_key
        if provider not in {"openai", "anthropic", "deepseek", "openrouter"}:
            raise ValueError("Unsupported provider")
        self.provider = provider
        self.model = model or settings.default_llm_model

    @contextmanager
    def _sandbox(self):
        """Private network, provider guard and worker command; everything is removed on exit."""
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
            command = [
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
            ]
            yield SimpleNamespace(
                docker=docker,
                command=command,
                secret=secret,
                remaining=lambda: max(1.0, deadline - time.monotonic()),
            )
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

    def _job(self, box, question, chunks, effort, stream):
        context = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, 1))
        job = {
            "apiKey": self.api_key,
            "provider": self.provider,
            "model": self.model,
            "guardSecret": box.secret,
            "serverSecret": secrets.token_urlsafe(32),
            "prompt": f"Câu hỏi: {question}\n\nNguồn:\n{context}",
        }
        if effort in EFFORTS:
            job["variant"] = effort
        if stream:
            job["stream"] = True
        return job

    def answer(self, question, chunks, effort=None):
        with self._sandbox() as box:
            job = self._job(box, question, chunks, effort, False)
            result = box.docker(box.command, input=json.dumps(job).encode(), timeout=115)
            return worker_answer(json.loads(result.stdout))

    def answer_stream(self, question, chunks, effort=None):
        """Yield text as the model writes it; raises the same safe errors as answer()."""
        with self._sandbox() as box:
            job = self._job(box, question, chunks, effort, True)
            proc = subprocess.Popen(
                ["docker", *box.command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            watchdog = threading.Timer(box.remaining(), proc.kill)
            watchdog.start()
            sent, final = "", None
            try:
                proc.stdin.write(json.dumps(job).encode())
                proc.stdin.close()
                for raw in proc.stdout:
                    line = json.loads(raw)
                    if isinstance(line.get("delta"), str):
                        sent += line["delta"]
                        yield line["delta"]
                    else:
                        final = line
            finally:
                watchdog.cancel()
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
            if final is None:
                raise ValueError("worker ended without an answer")
            answer = worker_answer(final)
            if answer.startswith(sent) and len(answer) > len(sent):
                yield answer[len(sent) :]
