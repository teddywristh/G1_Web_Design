#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
log_file="${1:-.data/cloud-demo/tunnel.log}"
[[ -r "$log_file" ]] || { echo "Không đọc được log tunnel: $log_file" >&2; exit 1; }
api_url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$log_file" | tail -1 || true)
[[ -n "$api_url" ]] || { echo 'Chưa tìm thấy địa chỉ Quick Tunnel trong log.' >&2; exit 1; }
curl -fsS --max-time 15 "$api_url/ready" >/dev/null || { echo 'API chưa sẵn sàng.' >&2; exit 1; }
command -v gh >/dev/null || { echo 'Cần GitHub CLI để cập nhật biến PUBLIC_API_URL.' >&2; exit 1; }
gh variable set PUBLIC_API_URL --repo teddywristh/G1_Web_Design --body "$api_url"
python scripts/build-firebase-hosting.py --api-url "$api_url"
firebase deploy --only hosting --project legal-ai-dev-aeb51 --non-interactive
echo "Đã cập nhật Firebase Hosting để dùng $api_url"
