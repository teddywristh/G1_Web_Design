#!/usr/bin/env bash
set -euo pipefail

# Checks the two OpenCode workers against a synthetic provider: the reasoning effort the backend asks for
# must reach the provider, and stream mode must print text deltas before the final line.
# Uses only synthetic credentials and a stub inside the container; never reads real credentials.
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
poc="$root_dir/scripts/opencode_poc"
worker_dir="$root_dir/apps/api/app/opencode_worker"
opencode_binary="${OPENCODE_POC_BINARY:-$(command -v opencode)}"
image_name="${OPENCODE_POC_IMAGE:-legal-api-backend:verify}"
common=(--rm -i --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 120
  --memory 512m --tmpfs /tmp:rw,nosuid,size=128m --tmpfs /app:rw,nosuid,size=8m --user 10001:10001
  --mount "type=bind,src=$opencode_binary,dst=/usr/local/bin/opencode,readonly"
  --mount "type=bind,src=$poc/fake_responses.py,dst=/opt/fake_responses.py,readonly")

failures=0
expect() { # name, expected substring, output
  if grep -q -- "$2" <<<"$3"; then echo "ok   $1"; else echo "FAIL $1: expected '$2' in:"; echo "$3"; failures=1; fi
}

# API-key worker (worker.py): run_worker <variant|-> <stream 0|1>
run_worker() {
  local job
  job="$(python3 - "$1" "$2" <<'PY'
import json, sys
variant, stream = sys.argv[1:3]
job = {"apiKey": "synthetic-key", "provider": "openai", "model": "gpt-5.6-luna", "guardSecret": "g",
       "serverSecret": "s", "prompt": "Câu hỏi: x"}
if variant != "-":
    job["variant"] = variant
if stream == "1":
    job["stream"] = True
print(json.dumps(job))
PY
)"
  docker run "${common[@]}" --network none --add-host guard:127.0.0.1 \
    --mount "type=bind,src=$worker_dir/worker.py,dst=/opt/worker.py,readonly" \
    --entrypoint sh "$image_name" -c 'python /opt/fake_responses.py & sleep 0.4; exec python /opt/worker.py' <<<"$job"
}
expect "worker: default effort is OpenCode's medium" 'effort=medium' "$(run_worker - 0)"
expect "worker: variant low reaches the provider" 'effort=low' "$(run_worker low 0)"
out="$(run_worker low 1)"
expect "worker: stream prints deltas" '"delta": "effort="' "$out"
expect "worker: stream ends with the answer" '"answer": "effort=low done"' "$out"

# ChatGPT worker (oauth_call.py)
run_oauth() {
  docker run "${common[@]}" --network none \
    --mount "type=bind,src=$worker_dir/oauth_call.py,dst=/opt/oauth_call.py,readonly" \
    --mount "type=bind,src=$poc/drive_oauth_call.py,dst=/opt/drive_oauth_call.py,readonly" \
    --entrypoint python "$image_name" /opt/drive_oauth_call.py <<<"$1"
}
base='{"action": "answer", "model": "gpt-5.6-luna", "prompt": "Câu hỏi: x"'
expect "oauth: variant low reaches the provider" 'effort=low' "$(run_oauth "$base, \"variant\": \"low\"}")"
out="$(run_oauth "$base, \"variant\": \"low\", \"stream\": true}")"
expect "oauth: stream prints deltas" '"delta": "effort="' "$out"
expect "oauth: stream ends with the answer" '"answer": "effort=low done"' "$out"
exit "$failures"
