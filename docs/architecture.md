# System architecture

The implemented backend MVP uses FastAPI, Firebase Authentication, Cloud Firestore and Firebase Storage. The product scope and original roadmap are described in `plans.md`; the backend implementation scope is [backend-plan.md](backend-plan.md). Open issue status is not the source of scope for this work.

```text
Web ── login ──► Firebase Authentication
 │
 └─ Bearer ID token ─► Edge gateway ─► FastAPI /api/v1
                       limits/TLS      │
                                     auth + active profile + role guard
                                       │
                                       router (Pydantic schemas)
                                       │
                                       service (business rules)
                                       ├─ repository ─► Firestore
                                       └─ private files ─► Firebase Storage
```

The frontend has no Admin SDK and does not directly read/write business collections or Storage. Firebase Auth is responsible for registration, sign-in, password reset and token refresh. Backend verifies tokens including revocation, reads active/role from the server-owned profile, and issues no separate session token.

## Boundaries

- `apps/api/app/api/v1/routes.py`: HTTP contract and download/upload transport.
- `apps/api/app/schemas`: strict request models and response allowlists.
- `apps/api/app/dependencies.py`: Firebase clients, current user, admin guard, If-Match parsing.
- `apps/api/app/services/users.py`: bootstrap and user updates.
- `apps/api/app/services/documents.py`: metadata, query construction, upload/delete saga and reconciliation.
- `apps/api/app/repositories/backend.py`: bounded Firestore query/cursor, transactional version checks via domain callbacks, atomic audit writes.
- `apps/api/app/core`: validated configuration, common Firebase init, auth and errors.
- `scripts/backend_admin.py`: project-targeted CLI with dry-run default.
- `infra/firebase`: deny-all client rules and explicit query indexes.
- `infra/nginx/api.conf`: single edge gateway rate/body/connection limits.

SDK calls use sync routes/dependencies or worker threads. Upload reads the HTTP stream into a bounded temporary file; download reads a generation-pinned object into a temporary file and sends an attachment. Files are private, and authorization happens for each request. No signed URL or public bucket access is needed.

Firestore transactions atomically write a versioned record and audit event. Storage cannot participate in that transaction: upload leases, unique object names, deletion tombstones and a dry-run reconciliation CLI provide recovery. This is a synchronous MVP, with no cache or broker dependency. Maintenance uses paged scans, never an entire collection in memory.

## Environment and delivery

Local development uses all three Firebase emulators with project demo-legal-api. Production rejects emulator configuration and wildcard CORS. Dev and production are separate projects. Runtime uses ADC/Workload Identity and least-privilege service accounts. CI runs lint/format/compile, domain/API tests and emulator integration/rules tests.

The public entry point must enforce TLS and rate limits. Docker Compose includes a gateway; a cloud deployment may use an equivalent central edge policy. Backend replicas must not be publicly reachable around that policy. Readiness checks dependencies separately from process health. See [operations](backend-operations.md) for rollout, quota monitoring, backup/restore and rollback.

## Excluded features

No LLM calls, AI feature, chat/history API, embedding/vector store, semantic search, OCR or document content extraction is introduced. Existing helpers for excluded domains are not wired into the API. PostgreSQL/Redis diagrams in historical planning do not describe this Firebase-first backend.
