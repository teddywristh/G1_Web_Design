"""Ephemeral per-user OpenCode server. Its credential store stays in container tmpfs."""

import json
import os
import shutil
import signal
import subprocess

signal.alarm(3600)
config = {
    "permission": "deny",
    "autoupdate": False,
    "share": "disabled",
    "enabled_providers": ["openai"],
    "agent": {"build": {"steps": 2}, "plan": {"steps": 2}},
}
if not os.path.isfile("/opt/models.json") and not os.path.isfile("/tmp/cache/opencode/models.json"):
    # The pinned binary's embedded catalog predates this model.
    config["provider"] = {"openai": {"models": {"gpt-5.6-luna": {"name": "GPT 5.6 Luna"}}}}
os.environ.update(
    {
        "HOME": "/tmp/home",
        "XDG_DATA_HOME": "/tmp/data",
        "XDG_CONFIG_HOME": "/tmp/config",
        "XDG_CACHE_HOME": "/tmp/cache",
        "XDG_STATE_HOME": "/tmp/state",
        "HTTPS_PROXY": "http://guard:9081",
        "HTTP_PROXY": "http://guard:9081",
        "NO_PROXY": "127.0.0.1,localhost",
        "OPENCODE_DISABLE_MODELS_FETCH": "true",
        "OPENCODE_CONFIG_CONTENT": json.dumps(config),
    }
)
if subprocess.check_output(["opencode", "--version"], text=True, timeout=5).strip() != "1.17.11":
    raise RuntimeError("OpenCode version mismatch")
if os.path.isfile("/opt/models.json"):
    os.makedirs("/tmp/cache/opencode", exist_ok=True)
    shutil.copyfile("/opt/models.json", "/tmp/cache/opencode/models.json")
os.chdir("/tmp")
os.execvp("opencode", ["opencode", "serve", "--hostname", "127.0.0.1", "--port", "4097", "--pure"])
