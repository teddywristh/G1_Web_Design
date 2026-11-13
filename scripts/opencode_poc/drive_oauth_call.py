"""Run oauth_call.py's answer action against fake_responses.py. Synthetic credentials only.

Starts the provider stub and an OpenCode server (as oauth_server.py would, minus the HTTPS proxy), then
feeds the job from stdin to oauth_call.py and prints what it prints.
"""

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

job = sys.stdin.read()
efforts = ("none", "minimal", "low", "medium", "high")
os.environ.update(
    {
        "HOME": "/tmp/home",
        "XDG_DATA_HOME": "/tmp/data",
        "XDG_CONFIG_HOME": "/tmp/config",
        "XDG_CACHE_HOME": "/tmp/cache",
        "XDG_STATE_HOME": "/tmp/state",
        "OPENCODE_DISABLE_MODELS_FETCH": "true",
        "OPENCODE_SERVER_PASSWORD": "poc",
        "OPENCODE_CONFIG_CONTENT": json.dumps(
            {
                "permission": "deny",
                "autoupdate": False,
                "share": "disabled",
                "enabled_providers": ["openai"],
                "provider": {
                    "openai": {
                        "options": {"baseURL": "http://127.0.0.1:9081/v1"},
                        "models": {
                            "gpt-5.6-luna": {
                                "name": "poc",
                                "variants": {e: {"reasoningEffort": e} for e in efforts},
                            }
                        },
                    }
                },
            }
        ),
    }
)
stub = subprocess.Popen(["python", "/opt/fake_responses.py"])
server = subprocess.Popen(
    ["opencode", "serve", "--hostname", "127.0.0.1", "--port", "4097", "--pure"],
    cwd="/tmp",
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
auth = "Basic " + base64.b64encode(b"opencode:poc").decode()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    request = urllib.request.Request(
        "http://127.0.0.1:4097" + path,
        method=method,
        headers={"Authorization": auth, "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    return json.load(opener.open(request, timeout=10))


try:
    for _ in range(200):
        try:
            if call("GET", "/global/health").get("healthy"):
                break
        except Exception:
            time.sleep(0.1)
    call("PUT", "/auth/openai", {"type": "api", "key": "synthetic-key"})
    result = subprocess.run(
        ["python", "/opt/oauth_call.py"], input=job, capture_output=True, text=True, timeout=60
    )
    sys.stdout.write(result.stdout)
finally:
    server.terminate()
    stub.terminate()
