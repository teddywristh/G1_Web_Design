# Development and operations scripts

`backend_admin.py` implements backend admin provisioning and Storage/Firestore reconciliation. Every invocation requires `--project` matching runtime configuration; default is dry-run and `--apply` enables writes. See [backend operations](../docs/backend-operations.md) for usage and recovery semantics.

`bootstrap_legal_ai_firestore.py` is the existing infrastructure bootstrap utility. Its scope is separate from backend admin provisioning; follow its existing instructions and confirm target project/credentials before cloud writes.

Backend scope and delivery are tracked against [backend-plan.md](../docs/backend-plan.md), not historical issue scope. Neither backend admin nor reconciliation runs AI processing.
