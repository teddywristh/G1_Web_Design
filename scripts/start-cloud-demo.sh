#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
state="$root/.data/cloud-demo"
mkdir -p "$state"
[[ -f apps/api/.env.cloud-backup ]] || { echo 'Missing apps/api/.env.cloud-backup'; exit 1; }
[[ -x .data/tools/cloudflared ]] || { echo 'Missing .data/tools/cloudflared'; exit 1; }
if curl -fsS --max-time 2 http://127.0.0.1:8002/health >/dev/null; then
  echo 'Port 8002 already serves an API; stop it before starting this demo.'; exit 1
fi
if ! curl -fsS --max-time 2 http://127.0.0.1:8010/ready >/dev/null; then
  echo 'Start the embedding service and wait until localhost:8010/ready succeeds.'; exit 1
fi
set -a
source apps/api/.env.cloud-backup
set +a
export APP_ENV=production FIREBASE_PROJECT_ID=legal-ai-dev-aeb51 FIREBASE_STORAGE_BUCKET=''
export STORAGE_BACKEND=local LOCAL_STORAGE_DIR="$state/storage"
export FIREBASE_AUTH_EMULATOR_HOST='' FIRESTORE_EMULATOR_HOST='' STORAGE_EMULATOR_HOST=''
export BACKEND_CORS_ORIGINS='["https://legal-ai-dev-aeb51.web.app","https://legal-ai-dev-aeb51.firebaseapp.com"]'
export AUTH_COOKIE_SECURE=true AUTH_COOKIE_SAMESITE=none EMBEDDING_PROVIDER=local
export OCR_FALLBACK_BINARY="$root/scripts/tesseract-local.sh"
export OCR_ENABLED=true OCR_SERVICE_URL="${OCR_SERVICE_URL:-http://127.0.0.1:8011}"
export OPENCODE_LOCAL_ENABLED=false OPENCODE_CHATGPT_LOCAL_ENABLED=false
export OPENCODE_CHATGPT_HOSTED_ENABLED=true OPENCODE_API_KEYS_HOSTED_ENABLED=true OPENCODE_BINARY="${OPENCODE_BINARY:-$HOME/.opencode/bin/opencode}"
nohup python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8002 > "$state/api.log" 2>&1 < /dev/null &
echo $! > "$state/api.pid"
nohup env PYTHONPATH=apps/api python -m app.workers.ingestion > "$state/worker.log" 2>&1 < /dev/null &
echo $! > "$state/worker.pid"
nohup .data/tools/cloudflared tunnel --url http://127.0.0.1:8002 --no-autoupdate > "$state/tunnel.log" 2>&1 < /dev/null &
echo $! > "$state/tunnel.pid"
echo "Services started. Once the tunnel is connected, run:"
echo 'bash scripts/publish-quick-tunnel.sh'
