"""Private single-job provider proxy with a fixed upstream per worker."""

import hmac
import http.client
import ipaddress
import json
import os
import signal
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PROVIDERS = {
    "openai": ("api.openai.com", "/v1/responses", "/v1/responses", "max_output_tokens"),
    "deepseek": ("api.deepseek.com", "/v1/chat/completions", "/v1/chat/completions", "max_tokens"),
    "openrouter": (
        "openrouter.ai",
        "/v1/chat/completions",
        "/api/v1/chat/completions",
        "max_tokens",
    ),
}
HOST, INPUT_PATH, UPSTREAM_PATH, MAX_FIELD = PROVIDERS[
    os.environ.get("OPENCODE_GUARD_PROVIDER", "openai")
]
SECRET = os.environ["OPENCODE_GUARD_SECRET"]
MAX_OUTPUT = int(os.environ.get("OPENCODE_MAX_OUTPUT_TOKENS", "2048"))
COUNT = 0
LOCK = threading.Lock()


class PinnedConnection(http.client.HTTPSConnection):
    def connect(self):
        addresses = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                continue
            try:
                raw = socket.create_connection((str(ip), 443), timeout=20)
                self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=HOST)
                return
            except OSError:
                continue
        raise OSError("provider unavailable")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def fail(self, status):
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def do_POST(self):
        global COUNT
        if urlsplit(self.path).path != INPUT_PATH or urlsplit(self.path).query:
            return self.fail(404)
        supplied = self.headers.get("x-worker-secret", "")
        if not supplied.isascii() or not hmac.compare_digest(supplied, SECRET):
            return self.fail(403)
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Bearer ") or len(authorization) > 4200:
            return self.fail(403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1_000_000:
                return self.fail(413)
        except ValueError:
            return self.fail(400)
        with LOCK:
            if COUNT >= 3:
                return self.fail(429)
            COUNT += 1
        connection = None
        try:
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                return self.fail(400)
            body[MAX_FIELD] = MAX_OUTPUT
            body = json.dumps(body).encode()
            connection = PinnedConnection(HOST, timeout=30)
            connection.request(
                "POST",
                UPSTREAM_PATH,
                body,
                headers={
                    "Authorization": authorization,
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
            )
            response = connection.getresponse()
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            total = 0
            while chunk := response.read1(8192):
                total += len(chunk)
                if total > 4_000_000:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (OSError, ValueError, http.client.HTTPException):
            self.close_connection = True
        finally:
            if connection:
                connection.close()


if __name__ == "__main__":
    signal.alarm(150)
    ThreadingHTTPServer(("0.0.0.0", 9081), Handler).serve_forever()
