#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
local_ocr="$root/.data/ocr/root/usr"
if [[ -x "$local_ocr/bin/tesseract" ]]; then
  export LD_LIBRARY_PATH="$local_ocr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export TESSDATA_PREFIX="${TESSDATA_PREFIX:-$local_ocr/share/tesseract-ocr/5/tessdata}"
  exec "$local_ocr/bin/tesseract" "$@"
fi
exec tesseract "$@"
