#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
opencode_binary="${OPENCODE_POC_BINARY:-$(command -v opencode)}"
image_name="${OPENCODE_POC_IMAGE:-legal-api-backend:verify}"
run_id="legal-opencode-poc-$$-$RANDOM"
net_a="$run_id-a"
net_b="$run_id-b"
guard_a="$run_id-guard-a"
guard_b="$run_id-guard-b"
cleanup() {
  docker rm -f "$guard_a" "$guard_b" >/dev/null 2>&1 || true
  docker network rm "$net_a" "$net_b" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create --internal "$net_a" >/dev/null
docker network create --internal "$net_b" >/dev/null
start_guard() {
  docker run -d --name "$1" --network "$2" --network-alias guard --user 10001:10001 \
    --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 80 --memory 128m \
    --tmpfs /tmp:rw,nosuid,size=32m -e "POC_USER=$3" -e "POC_ATTACK=${4:-0}" \
    --mount "type=bind,src=$root_dir/scripts/opencode_poc/private_guard.py,dst=/opt/private_guard.py,readonly" \
    --mount "type=bind,src=$root_dir/scripts/opencode_poc/mock_events.py,dst=/opt/mock_events.py,readonly" \
    --entrypoint python "$image_name" /opt/private_guard.py >/dev/null
  docker network connect bridge "$1"
}
start_guard "$guard_a" "$net_a" user-a
start_guard "$guard_b" "$net_b" user-b
# Use the specific internal network address, not the shared bridge address.
ip_a="$(docker inspect --format "{{(index .NetworkSettings.Networks \"$net_a\").IPAddress}}" "$guard_a")"
ip_b="$(docker inspect --format "{{(index .NetworkSettings.Networks \"$net_b\").IPAddress}}" "$guard_b")"
run_worker() {
  docker run --rm --network "$1" --read-only --cap-drop ALL --security-opt no-new-privileges \
    --pids-limit 80 --memory 512m --tmpfs /tmp:rw,nosuid,size=128m --tmpfs /app:rw,nosuid,size=8m \
    --user 10001:10001 -e "POC_USER=$2" -e "POC_OTHER_IP=$3" -e "POC_ATTACK=${4:-0}" \
    --mount "type=bind,src=$opencode_binary,dst=/usr/local/bin/opencode,readonly" \
    --mount "type=bind,src=$root_dir/scripts/opencode_poc/private_worker.py,dst=/opt/private_worker.py,readonly" \
    --entrypoint python "$image_name" /opt/private_worker.py
}
run_worker "$net_a" user-a "$ip_b" &
pid_a=$!
run_worker "$net_b" user-b "$ip_a" &
pid_b=$!
status=0
wait "$pid_a" || status=1
wait "$pid_b" || status=1
if [[ "$status" != 0 ]]; then exit "$status"; fi
# Recreate a dedicated guard for the adversarial provider response.
docker rm -f "$guard_a" >/dev/null
start_guard "$guard_a" "$net_a" attack bash
run_worker "$net_a" attack "$ip_b" bash
