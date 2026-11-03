#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${EMBEDDING_PYTHON:-.venv-embed/bin/python}"
exec "$PYTHON" -m uvicorn app.main:app --app-dir apps/embedding --host "${EMBEDDING_HOST:-127.0.0.1}" --port "${EMBEDDING_PORT:-8010}" --workers 1
