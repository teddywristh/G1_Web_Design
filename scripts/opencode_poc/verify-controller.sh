#!/usr/bin/env bash
set -euo pipefail
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
binary="${OPENCODE_POC_BINARY:-$(command -v opencode)}"
image="${OPENCODE_POC_IMAGE:-legal-api-backend:verify}"
run_id="legal-opencode-controller-$$-$RANDOM"
network="$run_id-net"
guard="$run_id-guard"
cleanup() {
  docker rm -f "$guard" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create --internal "$network" >/dev/null
docker run -d --rm --name "$guard" --network "$network" --network-alias guard --user 10001:10001 \
  --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 64 --memory 128m \
  --tmpfs /tmp:rw,nosuid,size=16m -e POC_USER=controller -e POC_GUARD_SECRET=test-secret \
  --mount "type=bind,src=$root_dir/scripts/opencode_poc/private_guard.py,dst=/opt/private_guard.py,readonly" \
  --mount "type=bind,src=$root_dir/scripts/opencode_poc/mock_events.py,dst=/opt/mock_events.py,readonly" \
  --entrypoint python "$image" /opt/private_guard.py >/dev/null
printf '%s' '{"apiKey":"sk-test-controller","model":"gpt-4o-mini","guardSecret":"test-secret","serverSecret":"test-server","prompt":"Synthetic legal question and source."}' | \
  docker run --rm -i --network "$network" --user 10001:10001 --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 80 --memory 512m --tmpfs /tmp:rw,nosuid,size=128m \
  --tmpfs /app:rw,nosuid,size=8m --mount "type=bind,src=$binary,dst=/usr/local/bin/opencode,readonly" \
  --mount "type=bind,src=$root_dir/apps/api/app/opencode_worker/worker.py,dst=/opt/worker.py,readonly" \
  --entrypoint python "$image" /opt/worker.py | \
  python -c 'import json,sys; d=json.load(sys.stdin); assert d.get("answer")=="Cau tra loi gia."; print("OpenCode production controller + fake provider: passed")'
