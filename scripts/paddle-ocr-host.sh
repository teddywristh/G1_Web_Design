#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export FLAGS_allocator_strategy="${FLAGS_allocator_strategy:-auto_growth}"
export FLAGS_fraction_of_gpu_memory_to_use="${FLAGS_fraction_of_gpu_memory_to_use:-0.15}"
export PADDLE_PDX_CACHE_HOME="${PADDLE_PDX_CACHE_HOME:-$PWD/.data/paddle-models}"
ocr_python="${PADDLE_OCR_PYTHON:-.data/paddle-ocr-venv/bin/python}"
cuda_dirs="$("$ocr_python" -c 'import glob, os, sys; print(":".join(p for root in sys.path for p in glob.glob(os.path.join(root, "nvidia", "*", "lib")) if os.path.isdir(p)))')"
export LD_LIBRARY_PATH="$cuda_dirs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$ocr_python" -m uvicorn app.main:app --app-dir apps/ocr --host 127.0.0.1 --port "${PADDLE_OCR_PORT:-8011}" --workers 1
