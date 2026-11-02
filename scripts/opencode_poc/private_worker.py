"""Synthetic OpenCode worker exercising an isolated guard/network boundary."""

import base64
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

user = os.environ["POC_USER"]
attack = os.environ.get("POC_ATTACK", "0")
other_guard = os.environ["POC_OTHER_IP"]
canary = "synthetic-secret-should-not-enter-provider-context"
Path("/tmp/canary-secret").write_text(canary)
config = {
    "permission": "deny",
    "autoupdate": False,
    "share": "disabled",
    "enabled_providers": ["openai"],
    "provider": {"openai": {"options": {"baseURL": "http://guard:9081/v1"}}},
}
env = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "XDG_DATA_HOME": "/tmp/data",
    "XDG_CONFIG_HOME": "/tmp/config",
    "XDG_CACHE_HOME": "/tmp/cache",
    "XDG_STATE_HOME": "/tmp/state",
    "OPENCODE_CONFIG_CONTENT": json.dumps(config),
    "OPENCODE_SERVER_PASSWORD": "test-only-password",
    "OPENCODE_DISABLE_MODELS_FETCH": "true",
}
assert (
    subprocess.check_output(
        ["/usr/local/bin/opencode", "--version"], env=env, text=True
    ).strip()
    == "1.17.11"
)
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
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(base, method, path, data=None, key=None, timeout=5):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = key
    req = urllib.request.Request(
        base + path,
        method=method,
        headers=headers,
        data=json.dumps(data).encode() if data is not None else None,
    )
    with opener.open(req, timeout=timeout) as response:
        return response.status, json.load(response)


def blocked(ip, port):
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex((ip, port)) != 0


try:
    auth = "Basic " + base64.b64encode(b"opencode:test-only-password").decode()
    base = "http://127.0.0.1:4096"
    for _ in range(120):
        try:
            assert call(base, "GET", "/global/health", key=auth)[1]["healthy"]
            break
        except OSError:
            if worker.poll() is not None:
                raise RuntimeError("OpenCode stopped during startup") from None
            time.sleep(0.1)
    else:
        raise RuntimeError("OpenCode startup timed out")
    assert os.getuid() != 0 and not os.path.exists("/var/run/docker.sock")
    assert not os.path.exists("/app/app")
    assert not os.path.exists(
        "/home/minhquang/.config/gcloud/application_default_credentials.json"
    )
    assert blocked("169.254.169.254", 80), "metadata service reachable"
    assert blocked("1.1.1.1", 443), "public network reachable without guard"
    assert blocked(other_guard, 9081), "other worker's guard reachable"
    key = "sk-test-" + user
    assert (
        call(base, "PUT", "/auth/openai", {"type": "api", "key": key}, auth)[0] == 200
    )
    session = call(base, "POST", "/session", {"title": "synthetic isolation"}, auth)[1][
        "id"
    ]
    question = {
        "model": {"providerID": "openai", "modelID": "gpt-4o-mini"},
        "parts": [{"type": "text", "text": "Synthetic legal question and context."}],
    }
    try:
        status, result = call(
            base, "POST", f"/session/{session}/message", question, auth, timeout=8
        )
        if attack == "0":
            assert status == 200 and any(
                p.get("text") == "Cau tra loi gia." for p in result.get("parts", [])
            )
    except TimeoutError:
        if attack == "0":
            raise
    if attack != "0":
        assert call(base, "POST", f"/session/{session}/abort", key=auth)[0] == 200
        time.sleep(1)
    stats = call("http://guard:9081", "GET", "/stats")[1]
    assert 1 <= stats["accepted"] <= 3 and stats["bad_key"] == 0
    assert not stats["canary"] and stats["tools"] == 0
    assert not Path("/tmp/unsafe-marker").exists()
    if attack != "0":
        assert stats["rejected"] > 0
        time.sleep(0.5)
        assert (
            call("http://guard:9081", "GET", "/stats")[1]["accepted"]
            == stats["accepted"]
        )
    assert call(base, "DELETE", f"/session/{session}", key=auth)[1] is True
    print(
        f"{user}: isolated network, peer/metadata/egress blocked; {stats['accepted']} mock calls, {stats['rejected']} blocked; fake key and tools verified",
        flush=True,
    )
finally:
    worker.terminate()
    try:
        worker.wait(timeout=4)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait()
