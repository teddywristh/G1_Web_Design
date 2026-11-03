#!/usr/bin/env bash
# Start missing local services without replacing an existing developer process.
set -euo pipefail
cd "$(dirname "$0")/.."
DEMO_PYTHON="${DEMO_PYTHON:-python}"
mkdir -p .data/local-demo
"$DEMO_PYTHON" - <<'PY'
import socket
for port in (9099, 8081, 9198):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=2): pass
    except OSError:
        raise SystemExit('Start Firebase emulators first: firebase emulators:start --project demo-legal-api --only auth,firestore,storage')
PY
if ! curl --silent --fail --max-time 3 http://127.0.0.1:8010/ready >/dev/null; then
  echo 'Embedding host must be ready first: bash scripts/embedding-host.sh'
  exit 1
fi
if ! curl --silent --fail --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
  nohup "$DEMO_PYTHON" -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 > .data/local-demo/api.log 2>&1 &
  echo "$!" > .data/local-demo/api.pid
fi
if ! pgrep -f '[p]ython.*-m app.workers.ingestion' >/dev/null; then
  nohup env PYTHONPATH=apps/api "$DEMO_PYTHON" -m app.workers.ingestion > .data/local-demo/worker.log 2>&1 &
  echo "$!" > .data/local-demo/worker.pid
fi
if ! curl --silent --fail --max-time 3 http://127.0.0.1:8085/index.html >/dev/null; then
  nohup "$DEMO_PYTHON" -m http.server 8085 --bind 127.0.0.1 --directory apps/web > .data/local-demo/web.log 2>&1 &
  echo "$!" > .data/local-demo/web.pid
fi
echo 'Open http://127.0.0.1:8085 and sign in. Backend: 8000; embeddings: 8010.'
