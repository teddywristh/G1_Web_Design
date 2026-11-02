"""Run inside an isolated container. All requests, credentials and text are synthetic."""

import base64
import json
import os
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

USER = os.environ["POC_USER"]
ATTACK = os.environ.get("POC_ATTACK", "0")
FAKE_KEY = "sk-test-" + USER
CANARY = "synthetic-secret-should-not-enter-provider-context"
requests_seen = []
budget_lock = threading.Lock()
budget = {"forwarded": 0, "blocked": 0}


from mock_events import event_stream


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        requests_seen.append(
            {
                "path": self.path,
                "key_matches": self.headers.get("Authorization")
                == "Bearer " + FAKE_KEY,
                "tools": len(body.get("tools") or []),
                "canary_leaked": CANARY in json.dumps(body),
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        try:
            for event in event_stream(ATTACK):
                self.wfile.write(
                    (
                        "event: "
                        + event["type"]
                        + "\ndata: "
                        + json.dumps(event)
                        + "\n\n"
                    ).encode()
                )
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


server = ThreadingHTTPServer(("127.0.0.1", 9080), Provider)
threading.Thread(target=server.serve_forever, daemon=True).start()


class BudgetProxy(BaseHTTPRequestHandler):
    """Synthetic limit experiment only; this is not an isolated production proxy."""

    def log_message(self, *_args):
        pass

    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        with budget_lock:
            if budget["forwarded"] >= 3:
                budget["blocked"] += 1
                self.send_error(429)
                return
            budget["forwarded"] += 1
        size = int(self.headers.get("Content-Length", "0"))
        request = urllib.request.Request(
            "http://127.0.0.1:9080/v1/responses",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": self.headers.get("Authorization", ""),
            },
            data=self.rfile.read(size),
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = response.read()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass


proxy = ThreadingHTTPServer(("127.0.0.1", 9081), BudgetProxy)
threading.Thread(target=proxy.serve_forever, daemon=True).start()
Path("/tmp/canary-secret").write_text(CANARY)
config = {
    "permission": "deny",
    "autoupdate": False,
    "share": "disabled",
    "enabled_providers": ["openai"],
    "provider": {"openai": {"options": {"baseURL": "http://127.0.0.1:9081/v1"}}},
}
env = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "XDG_DATA_HOME": "/tmp/data",
    "XDG_CONFIG_HOME": "/tmp/config",
    "XDG_CACHE_HOME": "/tmp/cache",
    "XDG_STATE_HOME": "/tmp/state",
    "OPENCODE_CONFIG_CONTENT": json.dumps(config),
    "OPENCODE_SERVER_PASSWORD": "test-only-server-password",
    "OPENCODE_DISABLE_MODELS_FETCH": "true",
}
assert (
    subprocess.check_output(
        ["/usr/local/bin/opencode", "--version"], env=env, text=True
    ).strip()
    == "1.17.11"
)
started = time.monotonic()
worker = subprocess.Popen(
    [
        "/usr/local/bin/opencode",
        "serve",
        "--hostname",
        "127.0.0.1",
        "--port",
        "4096",
        "--pure",
    ],
    cwd="/tmp",
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
base = "http://127.0.0.1:4096"
authorization = (
    "Basic " + base64.b64encode(b"opencode:test-only-server-password").decode()
)


def call(method, path, data=None, timeout=5):
    request = urllib.request.Request(
        base + path,
        method=method,
        headers={"Authorization": authorization, "Content-Type": "application/json"},
        data=json.dumps(data).encode() if data is not None else None,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.load(response)


try:
    for _ in range(100):
        try:
            assert call("GET", "/global/health")[1]["healthy"]
            break
        except (OSError, ValueError):
            if worker.poll() is not None:
                raise RuntimeError("worker exited during startup") from None
            time.sleep(0.1)
    else:
        raise RuntimeError("worker startup timed out")
    print(f"{USER}: startup {time.monotonic() - started:.2f}s", flush=True)
    assert call("PUT", "/auth/openai", {"type": "api", "key": FAKE_KEY})[0] == 200
    session = call("POST", "/session", {"title": "synthetic isolation check"})[1]["id"]
    assert len(call("GET", "/session")[1]) == 1
    assert os.getuid() != 0
    assert not os.path.exists("/app/app")
    assert not os.path.exists(
        "/home/minhquang/.config/gcloud/application_default_credentials.json"
    )
    assert not os.path.exists("/var/run/docker.sock")
    assert Path("/proc/net/route").read_text().count("\n") == 1
    question = {
        "model": {"providerID": "openai", "modelID": "gpt-4o-mini"},
        "parts": [
            {"type": "text", "text": "Synthetic legal question and synthetic context."}
        ],
    }
    began = time.monotonic()
    if ATTACK != "0":
        try:
            call("POST", f"/session/{session}/message", question, timeout=8)
        except TimeoutError:
            pass
        abort_status, _ = call("POST", f"/session/{session}/abort")
        assert abort_status == 200
        time.sleep(0.5)
        after_abort = len(requests_seen)
        time.sleep(0.5)
        assert len(requests_seen) == after_abort
        assert budget["forwarded"] <= 3
        assert budget["blocked"] > 0
        assert not os.path.exists("/tmp/unsafe-marker")
        print(
            f"{USER}: malicious {ATTACK}: {after_abort} calls forwarded, {budget['blocked']} blocked; abort stopped it",
            flush=True,
        )
    else:
        status, result = call("POST", f"/session/{session}/message", question)
        assert status == 200
        assert any(
            part.get("text") == "Cau tra loi gia." for part in result.get("parts", [])
        )
        assert not result.get("info", {}).get("error")
        print(
            f"{USER}: synthetic answer completed in {time.monotonic() - began:.2f}s",
            flush=True,
        )
    assert requests_seen and all(
        r
        == {
            "path": "/v1/responses",
            "key_matches": True,
            "tools": 0,
            "canary_leaked": False,
        }
        for r in requests_seen
    )
    assert call("DELETE", f"/session/{session}")[1] is True
    print(
        f"{USER}: fake key isolation, denied tools, no host files/network and cleanup passed",
        flush=True,
    )
finally:
    worker.terminate()
    try:
        worker.wait(timeout=4)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait()
    server.shutdown()
    proxy.shutdown()
