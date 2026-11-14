# Development and operations scripts

`backend_admin.py` implements backend admin provisioning and Storage/Firestore reconciliation. Every invocation requires `--project` matching runtime configuration; default is dry-run and `--apply` enables writes. See [backend operations](../docs/backend-operations.md) for usage and recovery semantics.

`bootstrap_legal_ai_firestore.py` is the existing infrastructure bootstrap utility. Its scope is separate from backend admin provisioning; follow its existing instructions and confirm target project/credentials before cloud writes.

Backend scope and delivery are tracked against [backend-plan.md](../docs/backend-plan.md), not historical issue scope. Neither backend admin nor reconciliation runs AI processing.

## Keeping the public API address alive

`tunnel-watchdog.sh` watches the Cloudflare Quick Tunnel that exposes the local API to the Firebase-hosted web app. A Quick Tunnel that loses its connection to Cloudflare's edge does not come back under the same address (the old address then answers `530`/`1033`). The watchdog checks `<tunnel>/health` every minute; after three failed checks in a row it stops the tunnel, starts a new one, waits until it answers, and runs `publish-quick-tunnel.sh` (updates the `PUBLIC_API_URL` Actions variable, rebuilds and deploys Hosting). Every few checks it also confirms that Hosting still shows the live address and republishes if not.

```bash
bash scripts/tunnel-watchdog.sh start    # background; log in .data/cloud-demo/watchdog.log
bash scripts/tunnel-watchdog.sh status   # tunnel, public check, local API, Hosting
bash scripts/tunnel-watchdog.sh stop
```

It leaves the tunnel alone while the local API itself is down (a new tunnel would not help), waits at least `WATCHDOG_COOLDOWN` seconds between recoveries and backs off up to 2 minutes if recovery keeps failing. Requires `curl`, `gh` (logged in), `firebase` (logged in), `python` and `.data/tools/cloudflared`. The settings are environment variables listed at the top of the script. It does not survive a reboot or a closed WSL session: start it again with the command above (or from `@reboot` in `crontab -e`).
