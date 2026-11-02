"""Single request OpenCode process. Credentials arrive over stdin, never argv."""

import base64
import json
import signal
import subprocess
import sys
import time
import urllib.request

signal.alarm(110)
worker = None


class WorkerFailure(Exception):
    pass


try:
    job = json.load(sys.stdin)
    provider = job.get("provider", "openai")
    if provider not in {"openai", "deepseek", "openrouter"}:
        raise ValueError("Unsupported provider")
    config = {
        "permission": "deny",
        "autoupdate": False,
        "share": "disabled",
        "enabled_providers": [provider],
        "provider": {
            provider: {
                "options": {
                    "baseURL": "http://guard:9081/v1",
                    "headers": {"x-worker-secret": job["guardSecret"]},
                }
            }
        },
    }
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "XDG_DATA_HOME": "/tmp/data",
        "XDG_CONFIG_HOME": "/tmp/config",
        "XDG_CACHE_HOME": "/tmp/cache",
        "XDG_STATE_HOME": "/tmp/state",
        "OPENCODE_CONFIG_CONTENT": json.dumps(config),
        "OPENCODE_SERVER_PASSWORD": job["serverSecret"],
        "OPENCODE_DISABLE_MODELS_FETCH": "true",
    }
    if (
        subprocess.check_output(
            ["/usr/local/bin/opencode", "--version"], env=env, text=True, timeout=5
        ).strip()
        != "1.17.11"
    ):
        raise RuntimeError("OpenCode version mismatch")
    worker = subprocess.Popen(
        ["/usr/local/bin/opencode", "serve", "--hostname", "127.0.0.1", "--port", "4096", "--pure"],
        cwd="/tmp",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    auth = "Basic " + base64.b64encode(("opencode:" + job["serverSecret"]).encode()).decode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(method, path, body=None, timeout=5):
        request = urllib.request.Request(
            "http://127.0.0.1:4096" + path,
            method=method,
            headers={"Authorization": auth, "Content-Type": "application/json"},
            data=json.dumps(body).encode() if body is not None else None,
        )
        with opener.open(request, timeout=timeout) as response:
            return json.load(response)

    for _ in range(150):
        try:
            if call("GET", "/global/health").get("healthy"):
                break
        except (OSError, ValueError):
            if worker.poll() is not None:
                raise RuntimeError("worker stopped") from None
            time.sleep(0.1)
    else:
        raise RuntimeError("worker startup timed out")
    call("PUT", "/auth/" + provider, {"type": "api", "key": job["apiKey"]})
    session = call("POST", "/session", {"title": "legal-ai"})["id"]
    try:
        result = call(
            "POST",
            f"/session/{session}/message",
            {
                "model": {"providerID": provider, "modelID": job["model"]},
                "system": "Bạn là trợ lý pháp lý. Chỉ trả lời dựa trên nguồn được cung cấp. Nếu không đủ căn cứ, hãy nói rõ. Không tự tạo điều luật hoặc trích dẫn.",
                "parts": [{"type": "text", "text": job["prompt"]}],
            },
            timeout=75,
        )
        info = result.get("info", {})
        error = info.get("error") or {}
        status = (error.get("data") or {}).get("statusCode")
        if status in (401, 403):
            raise WorkerFailure("ai_authentication_failed")
        if status == 429:
            raise WorkerFailure("ai_rate_limited")
        if error:
            raise WorkerFailure("ai_unavailable")
        if info.get("finish") != "stop":
            raise WorkerFailure("ai_incomplete")
        text = "\n".join(
            part["text"]
            for part in result.get("parts", [])
            if part.get("type") == "text" and isinstance(part.get("text"), str)
        ).strip()
        if not text:
            raise RuntimeError("empty response")
        print(json.dumps({"answer": text}, ensure_ascii=False), flush=True)
    finally:
        try:
            call("POST", f"/session/{session}/abort")
            call("DELETE", f"/session/{session}")
        except Exception:
            pass
except WorkerFailure as error:
    print(json.dumps({"error": str(error)}), flush=True)
except Exception:
    print(json.dumps({"error": "worker_failed"}), flush=True)
    sys.exit(1)
finally:
    if worker:
        worker.terminate()
        try:
            worker.wait(timeout=3)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()
