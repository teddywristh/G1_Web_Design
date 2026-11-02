import importlib.util
import json
import socket
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest


@pytest.fixture
def guard(monkeypatch):
    monkeypatch.setenv("OPENCODE_GUARD_SECRET", "fake-guard-secret")
    path = Path(__file__).resolve().parents[1] / "app/opencode_worker/guard.py"
    spec = importlib.util.spec_from_file_location("opencode_guard_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pinned_connection_rejects_private_addresses_and_uses_hostname_for_tls(guard, monkeypatch):
    monkeypatch.setattr(
        guard.socket,
        "getaddrinfo",
        lambda *_a, **_kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        ],
    )
    connect = Mock(return_value=object())
    wrap = Mock(return_value=object())
    monkeypatch.setattr(guard.socket, "create_connection", connect)
    monkeypatch.setattr(guard.ssl, "create_default_context", lambda: Mock(wrap_socket=wrap))
    connection = guard.PinnedConnection(guard.HOST, timeout=1)
    connection.connect()
    assert connect.call_args.args[0] == ("8.8.8.8", 443)
    assert wrap.call_args.kwargs["server_hostname"] == "api.openai.com"


def test_guard_fixed_path_secret_budget_and_output_limit(guard, monkeypatch):
    upstreams = []

    class Response:
        status = 200

        def getheader(self, _name, default=None):
            return default

        def read1(self, _size):
            return b""

    class Connection:
        def __init__(self, host, timeout):
            assert host == "api.openai.com"

        def request(self, method, path, body, headers):
            upstreams.append((method, path, json.loads(body), headers))

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(guard, "PinnedConnection", Connection)
    server = ThreadingHTTPServer(("127.0.0.1", 0), guard.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            headers = {"x-worker-secret": "fake-guard-secret", "Authorization": "Bearer sk-fake"}
            assert (
                client.post("/v1/responses?target=private", headers=headers, json={}).status_code
                == 404
            )
            assert (
                client.post(
                    "/v1/responses", headers={**headers, "x-worker-secret": "wrong"}, json={}
                ).status_code
                == 403
            )
            for _ in range(3):
                assert (
                    client.post(
                        "/v1/responses", headers=headers, json={"max_output_tokens": 999999}
                    ).status_code
                    == 200
                )
            assert client.post("/v1/responses", headers=headers, json={}).status_code == 429
        assert len(upstreams) == 3
        assert all(
            method == "POST" and path == "/v1/responses" and body["max_output_tokens"] == 2048
            for method, path, body, _ in upstreams
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    ("provider", "host", "path"),
    [
        ("deepseek", "api.deepseek.com", "/v1/chat/completions"),
        ("openrouter", "openrouter.ai", "/api/v1/chat/completions"),
    ],
)
def test_provider_guard_uses_only_fixed_upstream(monkeypatch, provider, host, path):
    monkeypatch.setenv("OPENCODE_GUARD_SECRET", "fake-guard-secret")
    monkeypatch.setenv("OPENCODE_GUARD_PROVIDER", provider)
    file = Path(__file__).resolve().parents[1] / "app/opencode_worker/guard.py"
    spec = importlib.util.spec_from_file_location("provider_guard_test", file)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    calls = []

    class Connection:
        def __init__(self, target, timeout):
            assert target == host

        def request(self, method, target, body, headers):
            calls.append((target, json.loads(body), headers))

        def getresponse(self):
            return Mock(
                status=200,
                getheader=Mock(return_value="application/json"),
                read1=Mock(return_value=b""),
            )

        def close(self):
            pass

    monkeypatch.setattr(guard, "PinnedConnection", Connection)
    server = ThreadingHTTPServer(("127.0.0.1", 0), guard.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            headers = {"x-worker-secret": "fake-guard-secret", "Authorization": "Bearer sk-fake"}
            assert client.post("/v1/responses", headers=headers, json={}).status_code == 404
            assert (
                client.post(
                    "/v1/chat/completions", headers=headers, json={"max_tokens": 99999}
                ).status_code
                == 200
            )
        assert calls[0][0] == path
        assert calls[0][1]["max_tokens"] == 2048
        assert "x-worker-secret" not in calls[0][2]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
