"""Call only this isolated container's OpenCode server; input arrives over stdin."""

import base64
import json
import os
import sys
import time
import urllib.request

job = json.load(sys.stdin)
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
    elif job["action"] == "answer":
        session = call("POST", "/session", {"title": "legal-ai"})["id"]
        try:
            result = call(
                "POST",
                f"/session/{session}/message",
                {
                    "model": {"providerID": "openai", "modelID": job["model"]},
                    "system": "Bạn là trợ lý pháp lý. Chỉ trả lời dựa trên nguồn được cung cấp. Nếu không đủ căn cứ, hãy nói rõ. Không tự tạo điều luật hoặc trích dẫn.",
                    "parts": [{"type": "text", "text": job["prompt"]}],
                },
                timeout=75,
            )
            info = result.get("info", {})
            error = info.get("error") or {}
            status = (error.get("data") or {}).get("statusCode")
            if status in (401, 403):
                print(json.dumps({"error": "ai_authentication_failed"}))
            elif status == 429:
                print(json.dumps({"error": "ai_rate_limited"}))
            elif error or info.get("finish") != "stop":
                print(json.dumps({"error": "ai_incomplete"}))
            else:
                text = "\n".join(
                    part["text"]
                    for part in result.get("parts", [])
                    if part.get("type") == "text" and isinstance(part.get("text"), str)
                ).strip()
                print(json.dumps({"answer": text}, ensure_ascii=False))
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
