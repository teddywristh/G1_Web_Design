# Firebase data schema

Backend MVP uses Firebase Authentication for identity, Cloud Firestore for records and Firebase Storage for private PDFs. FastAPI alone accesses business data; Admin SDK bypasses rules, so every protected route enforces authorization server-side. Client rules deny all Firestore/Storage operations.

## users/{uid}

ID is the Firebase Auth UID. Fields: email (nullable), displayName, role (`user`/`admin`), isActive, createdAt, updatedAt, version (positive integer). Bootstrap creates a user profile transactionally, default role user. Repeat bootstrap preserves all existing fields. Client PATCH only accepts displayName. Admin PATCH only accepts isActive; CLI provisions admin. Profile active state is enforced in addition to Firebase Auth revoked/disabled status.

## legal_documents/{documentId}

Server generates UUID hex IDs. Metadata: title, normalizedTitle, documentNumber, normalizedNumber, documentType, issuingAuthority, issueDate, effectiveDate (nullable), status, sourceUrl (nullable). Normalized title/number are lowercase, accent-insensitive, whitespace-normalized. Number is not a unique key.

Status: not_yet_effective, effective, partially_expired, expired; entered by admin, never inferred from dates. Dates are YYYY-MM-DD strings for predictable range queries, not Firestore timestamp values.

Storage lifecycle fields:

- fileState: pending_upload, available, upload_failed, deletion_pending, deleted.
- storagePath: private object path, nullable; only populated after upload completes.
- fileSize, contentType, sha256: populated by backend after successful upload.
- uploadLease: nullable `{id, path, expiresAt}` for a single upload attempt. Expiry is a UTC Firestore timestamp. Expired attempts must be reconciled before retrying; orphan objects are never published automatically.
- createdBy, updatedBy: server-owned actor UID.
- createdAt, updatedAt: Firestore server timestamps; version increments with every mutation.
- deletedAt: null while active, UTC timestamp once deletion requested. Public queries require explicit null and available fileState. Keep the tombstone after deleting object.

Object path: `legal-documents/{documentId}/{attemptId}.pdf`. Every attempt has a distinct name and create-only generation precondition. Delete is conditional on object generation. File data is never stored in Firestore. PDF replacement is not supported; create a new document.

## system_logs/{logId}

Server generates ID inside each transactional mutation. Fields: event, actorId, targetId, result (`success`/`failed`), requestId, createdAt (server timestamp). Upload failed/expired state transitions use failed result. Data mutation and its audit record commit together. No audit on idempotent no-op retry. Denied requests are recorded as structured HTTP logs instead.

Audit records do not contain token, email, request body or file content. Decide retention separately before enabling TTL. No client write/edit/delete access.

## Query contracts and concurrency

See [API contract](api-contract.md) for the supported filter matrix. Lists use limit 20 by default, max 100, and cursor with query fingerprint + ordering value + document ID. Queries request limit + 1 for nextCursor, use a deterministic ID tie-breaker, and do not scan collections to filter in Python. Missing/invalid cursor returns 422; cursor filters must match the original query. Cursor is not an authorization mechanism.

See `infra/firebase/firestore.indexes.json` for the exact indexes. API supports one selector per document query, optionally a two-sided issueDate range. No arbitrary filter combinations. Firestore and Storage operations have explicit timeouts and no unbounded client retries. Version comparison occurs inside a Firestore transaction; stale writes return 409. If-Match is mandatory for PATCH/PUT file/DELETE.

## Collections outside backend MVP

Existing `conversations/{conversationId}` and `conversations/{conversationId}/messages/{messageId}` repositories/collections remain outside this implementation. No chat/message endpoint, schema migration, or processing pipeline is added. Existing document processing fields are not interpreted or removed.
