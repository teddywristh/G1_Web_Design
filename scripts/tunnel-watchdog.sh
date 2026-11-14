#!/usr/bin/env bash
# Keeps the public address of the API alive: Cloudflare Quick Tunnels drop now and then, and a
# dropped one never comes back under the same address. The watchdog checks the public URL,
# and when it stays dead it starts a new tunnel, then republishes the address (GitHub variable
# PUBLIC_API_URL and Firebase Hosting) with scripts/publish-quick-tunnel.sh.
#
#   scripts/tunnel-watchdog.sh start    run in the background (log: .data/cloud-demo/watchdog.log)
#   scripts/tunnel-watchdog.sh stop
#   scripts/tunnel-watchdog.sh status
#   scripts/tunnel-watchdog.sh run      run in the foreground
#
# It never touches the API itself: if the local API does not answer, restarting the tunnel would
# not help, so it only logs that. Tuning (environment variables, seconds unless noted):
#   WATCHDOG_INTERVAL=60   time between checks
#   WATCHDOG_FAILS=3       consecutive failed checks before acting (ignores short glitches)
#   WATCHDOG_COOLDOWN=180  minimum time between two recoveries; doubles after each failed one
#   WATCHDOG_SYNC_EVERY=10 checks between "does Hosting still point at this tunnel?" (count)
#   WATCHDOG_API_PORT=8002 local port the tunnel forwards to
#   WATCHDOG_SITE_URL=https://legal-ai-dev-aeb51.web.app
set -uo pipefail # no -e: the loop has to survive any single failure
cd "$(dirname "$0")/.."
root="$PWD"
self="$root/scripts/tunnel-watchdog.sh"
state="$root/.data/cloud-demo"
mkdir -p "$state"
log="$state/watchdog.log"
publish_log="$state/watchdog-publish.log"
pidfile="$state/watchdog.pid"
tunnel_log="$state/tunnel-http2.log"
cloudflared="$root/.data/tools/cloudflared"
port="${WATCHDOG_API_PORT:-8002}"
interval="${WATCHDOG_INTERVAL:-60}"
need="${WATCHDOG_FAILS:-3}"
cooldown="${WATCHDOG_COOLDOWN:-180}"
sync_every="${WATCHDOG_SYNC_EVERY:-10}"
site="${WATCHDOG_SITE_URL:-https://legal-ai-dev-aeb51.web.app}"

say() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }
now() { date +%s; }
url_from_log() { grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$tunnel_log" 2>/dev/null | grep -v '^https://api\.' | tail -1; }
local_ok() { curl -fsS --max-time 5 "http://127.0.0.1:$port/health" 2>/dev/null | grep -q '"ok"'; }
healthy() { curl -fsS --max-time 10 "$1/health" 2>/dev/null | grep -q '"ok"'; }
site_points_at() { curl -fsS --max-time 15 "$site/" 2>/dev/null | grep -q -F "$1"; }
is_running() { [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; }

tunnel_pids() {
  local p
  for p in $(pgrep -x cloudflared); do
    tr '\0' ' ' <"/proc/$p/cmdline" 2>/dev/null | grep -q -- "--url http://127.0.0.1:$port" && echo "$p"
  done
}

stop_tunnel() {
  local p
  for p in $(tunnel_pids); do kill "$p" 2>/dev/null; done
  for _ in $(seq 20); do [[ -z "$(tunnel_pids)" ]] && return 0; sleep 0.5; done
  for p in $(tunnel_pids); do kill -9 "$p" 2>/dev/null; done
}

start_tunnel() {
  [[ -f "$tunnel_log" ]] && mv -f "$tunnel_log" "$tunnel_log.previous"
  setsid nohup "$cloudflared" tunnel --protocol http2 --url "http://127.0.0.1:$port" \
    --no-autoupdate >"$tunnel_log" 2>&1 </dev/null 9>&- & # 9: do not hold the watchdog lock
}

# The new tunnel is registered and answers on its public address. Returns at once if cloudflared
# has already exited (it does when registration with Cloudflare times out).
wait_public() {
  local end=$(($(now) + 70)) url
  while (($(now) < end)); do
    [[ -z "$(tunnel_pids)" ]] && return 1
    url="$(url_from_log)"
    if [[ -n "$url" ]] && grep -q "Registered tunnel connection" "$tunnel_log" 2>/dev/null && healthy "$url"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# publish-quick-tunnel.sh checks /ready once; on a flaky network that single check can fail.
publish() {
  local i
  : >"$publish_log"
  for i in 1 2 3 4 5; do
    if bash "$root/scripts/publish-quick-tunnel.sh" "$tunnel_log" >>"$publish_log" 2>&1; then return 0; fi
    say "publish attempt $i failed: $(tail -1 "$publish_log")"
    sleep 10
  done
  return 1
}

confirm_site() {
  local url="$1" i
  for i in 1 2 3 4 5 6; do
    site_points_at "$url" && return 0
    sleep 10
  done
  return 1
}

recover() {
  local attempt url
  for attempt in 1 2 3 4 5 6; do
    say "recovering (attempt $attempt): stopping the tunnel and starting a new one"
    stop_tunnel
    start_tunnel
    if wait_public; then break; fi
    say "the new tunnel did not come up"
    url=""
    sleep 3
  done
  url="$(url_from_log)"
  if [[ -z "$url" ]] || ! healthy "$url"; then say "no working tunnel after 6 attempts"; return 1; fi
  say "new tunnel $url is up; publishing it"
  if ! publish; then say "publishing failed; Hosting still points at the old address"; return 1; fi
  if confirm_site "$url"; then say "Hosting now points at $url"; else say "published, but $site does not show $url yet (CDN delay?)"; fi
  return 0
}

run() {
  exec 9>"$state/watchdog.lock"
  flock -n 9 || { echo "watchdog already running"; exit 0; }
  echo $$ >"$pidfile"
  trap 'say "watchdog stopped"; rm -f "$pidfile"; exit 0' INT TERM
  local cmd
  for cmd in curl gh firebase python; do
    command -v "$cmd" >/dev/null || { say "missing command: $cmd"; exit 1; }
  done
  [[ -x "$cloudflared" ]] || { say "missing $cloudflared"; exit 1; }
  say "watchdog started: every ${interval}s, acts after $need failed checks, port $port"
  local fails=0 backoff=0 last_recover=0 cycle=0 url noted=0
  while true; do
    cycle=$((cycle + 1))
    [[ -f "$log" && $(stat -c %s "$log") -gt 1048576 ]] && mv -f "$log" "$log.1"
    url="$(url_from_log)"
    if ! local_ok; then
      fails=0
      ((noted++ % 10 == 0)) && say "the API on :$port does not answer; leaving the tunnel alone"
    elif [[ -n "$url" ]] && healthy "$url"; then
      ((fails > 0)) && say "public address answers again without intervention"
      fails=0 noted=0
      if ((cycle % sync_every == 0)) && ! site_points_at "$url" && (($(now) - last_recover >= cooldown)); then
        say "Hosting does not show the live tunnel $url; republishing"
        last_recover="$(now)"
        publish && confirm_site "$url" && say "Hosting now points at $url"
      fi
    else
      fails=$((fails + 1))
      if [[ -z "$(tunnel_pids)" ]]; then fails=$need; say "the tunnel process is gone"; else say "public check failed ($fails/$need): ${url:-no address yet}"; fi
      if ((fails >= need && $(now) - last_recover >= cooldown + backoff)); then
        last_recover="$(now)"
        if recover; then fails=0 backoff=0; else backoff=$((backoff == 0 ? 30 : backoff * 2)); ((backoff > 120)) && backoff=120; say "next attempt in at least $((cooldown + backoff))s"; fi
      fi
    fi
    sleep "$interval" 9>&- &
    wait $! # so that "stop" takes effect at once instead of after the sleep
  done
}

case "${1:-status}" in
  run) run ;;
  start)
    if is_running; then echo "already running (pid $(cat "$pidfile"))"; exit 0; fi
    nohup setsid bash "$self" run >>"$log" 2>&1 </dev/null &
    sleep 2
    if is_running; then echo "started (pid $(cat "$pidfile")); log: $log"; else echo "did not start; see $log"; exit 1; fi
    ;;
  stop)
    if is_running; then kill "$(cat "$pidfile")" && echo stopped; else echo "not running"; fi
    ;;
  status)
    if is_running; then echo "running (pid $(cat "$pidfile"))"; else echo "not running"; fi
    url="$(url_from_log)"
    echo "tunnel address: ${url:-none}"
    if [[ -n "$url" ]] && healthy "$url"; then echo "public check: ok"; else echo "public check: FAILING"; fi
    if local_ok; then echo "local API :$port: ok"; else echo "local API :$port: FAILING"; fi
    site_points_at "${url:-none}" && echo "Hosting points at the tunnel: yes" || echo "Hosting points at the tunnel: NO"
    tail -n 5 "$log" 2>/dev/null
    true
    ;;
  *) echo "usage: $0 start|stop|status|run" >&2; exit 2 ;;
esac
