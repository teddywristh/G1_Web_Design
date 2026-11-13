"""Call only this isolated container's OpenCode server; input arrives over stdin."""

import base64
import json
import os
import sys
import threading
import time
import urllib.request

job = json.load(sys.stdin)
EFFORTS = ("none", "minimal", "low", "medium", "high")
auth = (
    "Basic "
    + base64.b64encode(("opencode:" + os.environ["OPENCODE_SERVER_PASSWORD"]).encode()).decode()
)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None, timeout=10):
    req = urllib.request.Request(
        "http://127.0.0.1:4097" + path,
        method=method,
        headers={"Authorization": auth, "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    with opener.open(req, timeout=timeout) as response:
        return json.load(response)


lock = threading.Lock()


def emit(line):
    with lock:
        print(json.dumps(line, ensure_ascii=False), flush=True)


def stored_credential():
    """The current OAuth entry; the provider may have rotated the refresh token during the call."""
    try:
        with open("/tmp/data/opencode/auth.json", encoding="utf-8") as f:
            credential = json.load(f).get("openai", {})
    except (OSError, ValueError):
        return None
    return credential if credential.get("type") == "oauth" else None


def send(session, body):
    """POST the message; with stream, forward text deltas from the event stream meanwhile."""
    path = f"/session/{session}/message"
    if not job.get("stream"):
        return call("POST", path, body, timeout=75)
    kinds, held, finished, ready = {}, {}, threading.Event(), threading.Event()

    def listen():
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:4097/event", headers={"Authorization": auth}
            )
            with opener.open(req, timeout=100) as response:
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


try:
    for _ in range(150):
        try:
            if call("GET", "/global/health").get("healthy"):
                break
        except (OSError, ValueError):
            time.sleep(0.1)
    else:
        raise RuntimeError("worker unavailable")
    if job["action"] == "start":
        result = call("POST", "/provider/openai/oauth/authorize", {"method": 1}, timeout=60)
        print(json.dumps(result))
    elif job["action"] == "finish":
        call("POST", "/provider/openai/oauth/callback", {"method": 1}, timeout=240)
        with open("/tmp/data/opencode/auth.json", encoding="utf-8") as f:
            credential = json.load(f).get("openai", {})
        print(json.dumps({"connected": credential.get("type") == "oauth"}))
    elif job["action"] == "export":
        with open("/tmp/data/opencode/auth.json", encoding="utf-8") as f:
            credential = json.load(f).get("openai", {})
        if credential.get("type") != "oauth":
            raise ValueError("OAuth credential unavailable")
        print(json.dumps({"credential": credential}))
    elif job["action"] == "restore":
        credential = job.get("credential")
        if not isinstance(credential, dict) or credential.get("type") != "oauth":
            raise ValueError("Invalid OAuth credential")
        call("PUT", "/auth/openai", credential)
        print(json.dumps({"restored": True}))
    elif job["action"] == "models":
        # OpenCode filters the OpenAI catalog to what a ChatGPT sign-in may use.
        providers = call("GET", "/config/providers", timeout=20).get("providers", [])
        openai = next((item for item in providers if item.get("id") == "openai"), {})
        models = [
            {"id": key, "name": value.get("name") or key}
            for key, value in (openai.get("models") or {}).items()
            if isinstance(value, dict)
        ]
        print(json.dumps({"models": models}, ensure_ascii=False))
    elif job["action"] == "answer":
        session = call("POST", "/session", {"title": "legal-ai"})["id"]
        try:
            message = {
                "model": {"providerID": "openai", "modelID": job["model"]},
                "system": "Bạn là trợ lý pháp lý. Chỉ trả lời dựa trên nguồn được cung cấp. Nếu không đủ căn cứ, hãy nói rõ. Không tự tạo điều luật hoặc trích dẫn.",
                "parts": [{"type": "text", "text": job["prompt"]}],
            }
            if job.get("variant") in EFFORTS:
                message["variant"] = job["variant"]
            result = send(session, message)
            info = result.get("info", {})
            error = info.get("error") or {}
            status = (error.get("data") or {}).get("statusCode")
            # The credential rides along so the backend needs no second exec to persist a rotation.
            credential = stored_credential()
            extra = {"credential": credential} if credential else {}
            if status in (401, 403):
                emit({"error": "ai_authentication_failed", **extra})
            elif status == 429:
                emit({"error": "ai_rate_limited", **extra})
            elif error or info.get("finish") != "stop":
                emit({"error": "ai_incomplete", **extra})
            else:
                text = "\n".join(
                    part["text"]
                    for part in result.get("parts", [])
                    if part.get("type") == "text" and isinstance(part.get("text"), str)
                ).strip()
                emit({"answer": text, **extra})
        finally:
            try:
                call("POST", f"/session/{session}/abort")
                call("DELETE", f"/session/{session}")
            except Exception:
                pass
    else:
        raise ValueError("unknown action")
except Exception:
    print(json.dumps({"error": "worker_failed"}))
    sys.exit(1)
