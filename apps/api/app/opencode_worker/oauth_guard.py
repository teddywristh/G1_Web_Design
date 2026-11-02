"""Single-user HTTPS tunnel: OpenCode can only reach specified public OpenAI hosts."""

import ipaddress
import select
import signal
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED = {"auth.openai.com", "chatgpt.com", "api.openai.com"}
LOCK = threading.Lock()
COUNT = 0


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_CONNECT(self):
        global COUNT
        host, sep, port = self.path.partition(":")
        if not sep or host not in ALLOWED or port != "443":
            return self.send_error(403)
        with LOCK:
            if COUNT >= 100:
                return self.send_error(429)
            COUNT += 1
        upstream = None
        try:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            address = next(
                (item[4][0] for item in addresses if ipaddress.ip_address(item[4][0]).is_global),
                None,
            )
            if not address:
                return self.send_error(502)
            upstream = socket.create_connection((address, 443), timeout=20)
            self.send_response(200, "Connection Established")
            self.end_headers()
            sockets = [self.connection, upstream]
            while True:
                ready, _, _ = select.select(sockets, [], [], 75)
                if not ready:
                    break
                for current in ready:
                    data = current.recv(65536)
                    if not data:
                        return
                    (upstream if current is self.connection else self.connection).sendall(data)
        except OSError:
            pass
        finally:
            if upstream:
                upstream.close()


if __name__ == "__main__":
    signal.alarm(3600)
    ThreadingHTTPServer(("0.0.0.0", 9081), Handler).serve_forever()
