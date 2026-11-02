#!/usr/bin/env bash
set -euo pipefail

# Uses only synthetic credentials and an in-container provider stub; never reads real credentials.
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
opencode_binary="${OPENCODE_POC_BINARY:-$(command -v opencode)}"
image_name="${OPENCODE_POC_IMAGE:-legal-api-backend:verify}"
run_worker() {
  docker run --rm --network none --read-only --cap-drop ALL \
    --security-opt no-new-privileges --pids-limit 80 --memory 512m \
    --tmpfs /tmp:rw,nosuid,size=128m --tmpfs /app:rw,nosuid,size=8m \
    --user 10001:10001 -e "POC_USER=$1" -e "POC_ATTACK=${2:-0}" \
    --mount "type=bind,src=$opencode_binary,dst=/usr/local/bin/opencode,readonly" \
    --mount "type=bind,src=$root_dir/scripts/opencode_poc/probe.py,dst=/opt/probe.py,readonly" \
    --mount "type=bind,src=$root_dir/scripts/opencode_poc/mock_events.py,dst=/opt/mock_events.py,readonly" \
    --entrypoint python "$image_name" /opt/probe.py
}
run_worker user-a &
first_pid=$!
run_worker user-b &
second_pid=$!
status=0
wait "$first_pid" || status=1
wait "$second_pid" || status=1
if [[ "$status" != 0 ]]; then exit "$status"; fi
run_worker attack-bash bash
run_worker attack-read read
