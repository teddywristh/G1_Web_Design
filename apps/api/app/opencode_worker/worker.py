"""Single request OpenCode process. Credentials arrive over stdin, never argv.

Output is one JSON line (`{"answer": ...}` or `{"error": ...}`), or with `stream` set a series of
`{"delta": ...}` lines followed by the same final line.
"""

import base64
import json
import signal
import subprocess
import sys
import threading
import time
import urllib.request

signal.alarm(110)
worker = None
EFFORTS = ("none", "minimal", "low", "medium", "high")


class WorkerFailure(Exception):
    pass


try:
    job = json.load(sys.stdin)
    provider = job.get("provider", "openai")
    if provider not in {"openai", "anthropic", "deepseek", "openrouter"}:
        raise ValueError("Unsupported provider")
    # Reasoning effort is an OpenAI option; other providers keep their own defaults.
    variant = job.get("variant") if provider == "openai" and job.get("variant") in EFFORTS else None
    model = {"name": job["model"]}
    if provider == "openai":
        model["variants"] = {effort: {"reasoningEffort": effort} for effort in EFFORTS}
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
                },
                # Models listed live by the provider may postdate the binary's bundled catalog.
                "models": {job["model"]: model},
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

    lock = threading.Lock()

    def emit(line):
        with lock:
            print(json.dumps(line, ensure_ascii=False), flush=True)

    def send(session, body):
        """POST the message; with stream, forward text deltas from the event stream meanwhile."""
        path = f"/session/{session}/message"
        if not job.get("stream"):
            return call("POST", path, body, timeout=75)
        kinds, held, finished = {}, {}, threading.Event()
        ready = threading.Event()

        def listen():
            try:
                request = urllib.request.Request(
                    "http://127.0.0.1:4096/event", headers={"Authorization": auth}
                )
                with opener.open(request, timeout=100) as response:
                    ready.set()
                    for raw in response:
                        if finished.is_set():
                            return
                        line = raw.decode("utf-8", "replace").strip()
                        if not line.startswith("data:"):
                            continue
                        try:
                            event = json.loads(line[5:])
                        except ValueError:
                            continue
                        props = event.get("properties") or {}
                        if props.get("sessionID") != session:
                            continue
                        kind = event.get("type")
                        if kind == "message.part.updated":
                            part = props.get("part") or {}
                            kinds[part.get("id")] = part.get("type")
                            for text in held.pop(part.get("id"), []):
                                if part.get("type") == "text":
                                    emit({"delta": text})
                        elif kind == "message.part.delta" and props.get("field") == "text":
                            part_id, text = props.get("partID"), props.get("delta")
                            if not isinstance(text, str):
                                continue
                            if kinds.get(part_id) == "text":
                                emit({"delta": text})
                            elif part_id not in kinds:
                                held.setdefault(part_id, []).append(text)
            except Exception:
                pass
            finally:
                ready.set()

        threading.Thread(target=listen, daemon=True).start()
        ready.wait(5)
        try:
            return call("POST", path, body, timeout=75)
        finally:
            time.sleep(0.15)  # let the last deltas drain before the final line is printed
            finished.set()

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
        message = {
            "model": {"providerID": provider, "modelID": job["model"]},
            "system": "Bạn là trợ lý pháp lý. Chỉ trả lời dựa trên nguồn được cung cấp. Nếu không đủ căn cứ, hãy nói rõ. Không tự tạo điều luật hoặc trích dẫn.",
            "parts": [{"type": "text", "text": job["prompt"]}],
        }
        if variant:
            message["variant"] = variant
        result = send(session, message)
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
        emit({"answer": text})
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
