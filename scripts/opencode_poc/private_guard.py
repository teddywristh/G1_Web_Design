"""Synthetic request-limiting guard: never connect to real providers."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mock_events import event_stream

expected = "Bearer sk-test-" + os.environ["POC_USER"]
attack = os.environ.get("POC_ATTACK", "0")
metrics = {"accepted": 0, "rejected": 0, "bad_key": 0, "tools": 0, "canary": False}
lock = threading.Lock()


class Guard(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path != "/stats":
            self.send_error(404)
            return
        with lock:
            data = json.dumps(metrics).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        guard_secret = os.environ.get("POC_GUARD_SECRET")
        if guard_secret and self.headers.get("x-worker-secret") != guard_secret:
            self.send_error(403)
            return
        if self.headers.get("Authorization") != expected:
            with lock:
                metrics["bad_key"] += 1
            self.send_error(403)
            return
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 1_000_000:
            self.send_error(413)
            return
        body = json.loads(self.rfile.read(size))
        with lock:
            if metrics["accepted"] >= 3:
                metrics["rejected"] += 1
                self.send_error(429)
                return
            metrics["accepted"] += 1
            metrics["tools"] += len(body.get("tools") or [])
            metrics["canary"] |= (
                "synthetic-secret-should-not-enter-provider-context" in json.dumps(body)
            )
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        try:
            for event in event_stream(attack):
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
        except (BrokenPipeError, ConnectionResetError):
            pass


ThreadingHTTPServer(("0.0.0.0", 9081), Guard).serve_forever()
