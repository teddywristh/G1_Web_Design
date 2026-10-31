"""Document metadata and recoverable, versioned PDF storage lifecycle."""

import unicodedata
from datetime import timedelta
from uuid import uuid4

from google.api_core.exceptions import NotFound, PreconditionFailed

from app.core.config import get_settings
from app.core.errors import APIError
from app.repositories.backend import utcnow
from app.services.users import check_version


def normalize(value):
    text = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def metadata(data):
    fields = dict(data)
    if "title" in fields:
        fields["normalizedTitle"] = normalize(fields["title"])
    if "documentNumber" in fields:
        fields["normalizedNumber"] = normalize(fields["documentNumber"])
    return fields


def ensure_document(current, *, public=False):
    if not current or current.get("deletedAt") is not None:
        raise APIError(404, "not_found", "Document not found")
    if public and current.get("fileState") != "available":
        raise APIError(404, "not_found", "Document not found")
    return current


def create_document(repo, data, actor, request_id):
    doc_id = uuid4().hex
    fields = {
        **metadata(data),
        "fileState": "pending_upload",
        "deletedAt": None,
        "createdBy": actor,
        "updatedBy": actor,
        "storagePath": None,
        "fileSize": None,
        "contentType": None,
        "uploadLease": None,
    }
    return repo.mutate(
        "legal_documents",
        doc_id,
        lambda _: fields,
        actor=actor,
        event="document.create",
        request_id=request_id,
    )


def patch_document(repo, doc_id, data, actor, request_id, version):
    def change(current):
        ensure_document(current)
        check_version(current, version)
        return {**metadata(data), "updatedBy": actor}

    return repo.mutate(
        "legal_documents",
        doc_id,
        change,
        actor=actor,
        event="document.update",
        request_id=request_id,
    )


def list_documents(repo, params, *, admin=False):
    filters = []
    if not admin:
        filters.extend([("deletedAt", "==", None), ("fileState", "==", "available")])
    order, descending = "createdAt", True
    if params.documentNumber:
        filters.append(("normalizedNumber", "==", normalize(params.documentNumber)))
    elif params.titlePrefix:
        title = normalize(params.titlePrefix)
        if not title:
            raise APIError(422, "invalid_query", "Title prefix is empty after normalization")
        filters.extend(
            [("normalizedTitle", ">=", title), ("normalizedTitle", "<=", title + "\uf8ff")]
        )
        order, descending = "normalizedTitle", False
    elif params.documentType:
        filters.append(("documentType", "==", params.documentType))
    elif params.issuingAuthority:
        filters.append(("issuingAuthority", "==", params.issuingAuthority))
    elif params.status:
        filters.append(("status", "==", params.status.value))
    elif params.issueDateFrom or params.issueDateTo:
        order = "issueDate"
        if params.issueDateFrom:
            filters.append(("issueDate", ">=", params.issueDateFrom.isoformat()))
        if params.issueDateTo:
            filters.append(("issueDate", "<=", params.issueDateTo.isoformat()))
    return repo.page(
        "legal_documents",
        filters=filters,
        order=order,
        descending=descending,
        limit=params.limit,
        cursor=params.cursor,
    )


def upload_document(repo, bucket, doc_id, path, size, digest, actor, request_id, version):
    settings = get_settings()
    attempt = uuid4().hex
    object_path = f"legal-documents/{doc_id}/{attempt}.pdf"

    def claim(current):
        ensure_document(current)
        if current.get("fileState") == "available":
            if current.get("sha256") == digest:
                return None
            raise APIError(409, "file_exists", "Create a new document to replace a PDF")
        check_version(current, version)
        lease = current.get("uploadLease")
        if lease:
            raise APIError(
                409,
                "upload_in_progress",
                "Run reconciliation for an expired upload before retrying",
            )
        return {
            "uploadLease": {
                "id": attempt,
                "path": object_path,
                "expiresAt": utcnow() + timedelta(seconds=settings.upload_lease_seconds),
            },
            "fileState": "pending_upload",
            "updatedBy": actor,
        }

    claimed = repo.mutate(
        "legal_documents",
        doc_id,
        claim,
        actor=actor,
        event="document.upload_claim",
        request_id=request_id,
    )
    if claimed["fileState"] == "available":
        return claimed
    blob = bucket.blob(object_path)
    try:
        blob.upload_from_filename(
            path,
            content_type="application/pdf",
            if_generation_match=0,
            timeout=settings.storage_timeout_seconds,
            retry=None,
        )
    except Exception:
        # Keep a potentially committed object discoverable until reconciliation.
        def fail(current):
            if ((current or {}).get("uploadLease") or {}).get("id") != attempt:
                return None
            return {"fileState": "upload_failed", "updatedBy": actor}

        repo.mutate(
            "legal_documents",
            doc_id,
            fail,
            actor=actor,
            event="document.upload_failed",
            request_id=request_id,
        )
        raise APIError(
            503, "storage_unavailable", "Upload failed; reconcile before retrying"
        ) from None

    def complete(current):
        ensure_document(current)
        if (current.get("uploadLease") or {}).get("id") != attempt:
            raise APIError(409, "upload_conflict", "Upload lease no longer belongs to this request")
        return {
            "storagePath": object_path,
            "fileState": "available",
            "fileSize": size,
            "sha256": digest,
            "contentType": "application/pdf",
            "uploadLease": None,
            "updatedBy": actor,
        }

    # If this transaction fails the lease retains the object for reconciliation.
    return repo.mutate(
        "legal_documents",
        doc_id,
        complete,
        actor=actor,
        event="document.upload_complete",
        request_id=request_id,
    )


def delete_document(repo, bucket, doc_id, actor, request_id, version):
    def mark(current):
        if not current:
            raise APIError(404, "not_found", "Document not found")
        if current.get("fileState") == "deleted":
            return None
        check_version(current, version)
        lease = current.get("uploadLease")
        if lease and lease["expiresAt"] > utcnow():
            raise APIError(409, "upload_in_progress", "Wait for upload to finish before deleting")
        return {
            "deletedAt": current.get("deletedAt") or utcnow(),
            "fileState": "deletion_pending",
            "updatedBy": actor,
        }

    current = repo.mutate(
        "legal_documents",
        doc_id,
        mark,
        actor=actor,
        event="document.delete_requested",
        request_id=request_id,
    )
    if current["fileState"] != "deleted":
        finish_deletion(repo, bucket, current, actor, request_id)
    return repo.get("legal_documents", doc_id)


def delete_object(bucket, path):
    if not path:
        return
    blob = bucket.blob(path)
    try:
        blob.reload(timeout=10, retry=None)
        blob.delete(if_generation_match=blob.generation, timeout=10, retry=None)
    except NotFound:
        pass


def finish_deletion(repo, bucket, current, actor, request_id):
    if current.get("fileState") != "deletion_pending":
        return
    paths = {current.get("storagePath"), (current.get("uploadLease") or {}).get("path")}
    for path in paths:
        delete_object(bucket, path)

    def finish(latest):
        if not latest or latest.get("fileState") != "deletion_pending":
            return None
        check_version(latest, current["version"])
        return {
            "fileState": "deleted",
            "storagePath": None,
            "uploadLease": None,
            "updatedBy": actor,
        }

    repo.mutate(
        "legal_documents",
        current["id"],
        finish,
        actor=actor,
        event="document.delete_complete",
        request_id=request_id,
    )


def reconcile(repo, bucket, *, dry_run=True):
    """Safe by default. In-flight leases are retained; stale writes are fenced by ID."""
    settings = get_settings()
    results = {"expiredUploads": 0, "pendingDeletions": 0, "orphanFiles": 0, "errors": 0}
    for current in repo.scan("legal_documents"):
        try:
            if current.get("fileState") == "deletion_pending":
                results["pendingDeletions"] += 1
                if not dry_run:
                    finish_deletion(repo, bucket, current, "maintenance", "reconcile")
            lease = current.get("uploadLease")
            if lease and lease["expiresAt"] < utcnow() and current.get("deletedAt") is None:
                results["expiredUploads"] += 1
                if not dry_run:
                    # Fence the uploader before touching its object.
                    def fence(latest):
                        check_version(latest, current["version"])
                        if (latest.get("uploadLease") or {}).get("id") != lease["id"]:
                            raise APIError(409, "upload_conflict", "Upload changed")
                        return {"uploadLease": None, "fileState": "upload_failed"}

                    repo.mutate(
                        "legal_documents",
                        current["id"],
                        fence,
                        actor="maintenance",
                        event="document.upload_expired",
                        request_id="reconcile",
                    )
                    delete_object(bucket, lease["path"])
        except Exception:
            results["errors"] += 1
    # Streaming iterator pages objects internally; never collect all files in RAM.
    for blob in bucket.list_blobs(prefix="legal-documents/", page_size=100, timeout=30, retry=None):
        try:
            if (
                not blob.time_created
                or (utcnow() - blob.time_created).total_seconds() < settings.orphan_grace_seconds
            ):
                continue
            parts = blob.name.split("/")
            if len(parts) != 3:
                continue
            doc = repo.get("legal_documents", parts[1])
            retained = doc and (
                doc.get("storagePath") == blob.name
                or (doc.get("uploadLease") or {}).get("path") == blob.name
            )
            if not retained:
                results["orphanFiles"] += 1
                if not dry_run:
                    blob.delete(if_generation_match=blob.generation, timeout=10, retry=None)
        except (NotFound, PreconditionFailed):
            continue
        except Exception:
            results["errors"] += 1
    return results
