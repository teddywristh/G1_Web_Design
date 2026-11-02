"""Knowledge bases, private documents, processing state and publication."""

from uuid import uuid4

from app.core.errors import APIError
from app.ingestion import pipeline
from app.repositories.backend import utcnow
from app.search.base import profile_from
from app.services import documents
from app.services.users import check_version

SHARED = pipeline.SHARED_KB
RETRYABLE = {"failed", "needs_configuration"}
PUBLIC_STATUS = {
    "queued": "queued",
    "running": "processing",
    "retry_wait": "processing",
    "succeeded": "ready",
    "needs_review": "needs_review",
    "needs_ocr": "needs_ocr",
    "needs_configuration": "failed",
    "failed": "failed",
    "cancelled": "revoked",
}
NEXT_ACTION = {
    "needs_configuration": "configure_ai_key",
    "needs_ocr": "upload_text_pdf",
    "needs_review": "await_admin_review",
}


def ensure_shared_kb(repo, request_id):
    def change(current):
        if current:
            return None
        return {
            "kind": "shared",
            "ownerUid": None,
            "title": "Kho luật dùng chung",
            "state": "active",
            "activeIndexGeneration": None,
            "latestGeneration": None,
            "embeddingProfileId": None,
            "deletedAt": None,
        }

    return repo.mutate(
        "knowledge_bases", SHARED, change, actor="system", event="kb.shared", request_id=request_id
    )


def kb_out(kb):
    return {**kb, "ready": bool(kb.get("activeIndexGeneration"))}


def create_kb(repo, user, title, request_id, settings):
    owned = repo.query(
        "knowledge_bases",
        [("ownerUid", "==", user["id"]), ("deletedAt", "==", None)],
        limit=settings.max_private_kbs,
    )
    if len(owned) >= settings.max_private_kbs:
        raise APIError(409, "quota_exceeded", "Private knowledge base limit reached")
    fields = {
        "kind": "private",
        "ownerUid": user["id"],
        "title": title,
        "state": "active",
        "activeIndexGeneration": None,
        "latestGeneration": None,
        "embeddingProfileId": None,
        "deletedAt": None,
    }
    created = repo.mutate(
        "knowledge_bases",
        uuid4().hex,
        lambda _: fields,
        actor=user["id"],
        event="kb.create",
        request_id=request_id,
    )
    return kb_out(created)


def list_kbs(repo, user, settings):
    shared = repo.get("knowledge_bases", SHARED)
    private = repo.query(
        "knowledge_bases",
        [("ownerUid", "==", user["id"]), ("deletedAt", "==", None)],
        limit=settings.max_private_kbs,
    )
    return [kb_out(kb) for kb in ([shared] if shared else []) + private]


def kb_for_user(repo, user, kb_id):
    """Other users' private KBs look exactly like missing ones."""
    kb = repo.get("knowledge_bases", kb_id)
    if not kb or kb.get("deletedAt") is not None:
        raise APIError(404, "not_found", "Knowledge base not found")
    if kb["kind"] == "private" and kb["ownerUid"] != user["id"]:
        raise APIError(404, "not_found", "Knowledge base not found")
    return kb


def private_document(repo, user, kb_id, doc_id):
    kb = kb_for_user(repo, user, kb_id)
    document = repo.get("knowledge_documents", doc_id)
    if kb["kind"] != "private" or not document or document["kbId"] != kb_id:
        raise APIError(404, "not_found", "Document not found")
    return documents.ensure_document(document)


def create_document(repo, user, kb_id, data, request_id):
    kb = kb_for_user(repo, user, kb_id)
    if kb["kind"] != "private":
        raise APIError(403, "forbidden", "Shared documents are managed by administrators")
    fields = {
        **data,
        "kbId": kb_id,
        "ownerUid": user["id"],
        "fileState": "pending_upload",
        "deletedAt": None,
        "createdBy": user["id"],
        "updatedBy": user["id"],
        "storagePath": None,
        "fileSize": None,
        "contentType": None,
        "uploadLease": None,
        "trust": "unverified",
    }
    return repo.mutate(
        "knowledge_documents",
        uuid4().hex,
        lambda _: fields,
        actor=user["id"],
        event="knowledge_document.create",
        request_id=request_id,
    )


def list_documents(repo, user, kb_id, limit, cursor):
    kb = kb_for_user(repo, user, kb_id)
    if kb["kind"] != "private":
        raise APIError(404, "not_found", "Knowledge base not found")
    return repo.page(
        "knowledge_documents",
        filters=[("kbId", "==", kb_id), ("deletedAt", "==", None)],
        limit=limit,
        cursor=cursor,
    )


def upload_options(user, kb_id, doc_id, credential_source, settings):
    return {
        "collection": "knowledge_documents",
        "prefix": "knowledge-documents",
        "outbox": pipeline.job_outbox(
            kb_id, "knowledge_documents", doc_id, user["id"], credential_source, settings
        ),
    }


def find_job(repo, document, settings):
    if document.get("fileState") != "available":
        return None
    key = pipeline.job_id(
        document["kbId"], document["id"], document["sha256"], profile_from(settings).id
    )
    return repo.get("processing_jobs", key)


def processing(repo, document, settings):
    job = find_job(repo, document, settings)
    if not job:
        return {"status": "queued", "stage": "upload", "legalValidity": "unknown"}
    return {
        "status": PUBLIC_STATUS[job["status"]],
        "stage": job["stage"],
        "errorCode": job.get("errorCode"),
        "retryable": job["status"] in RETRYABLE,
        "nextAction": NEXT_ACTION.get(job["status"]),
        "warnings": job.get("warnings", []),
        "legalValidity": "unknown",
    }


def reprocess(repo, document, user, version, request_id, settings):
    check_version(document, version)
    job = find_job(repo, document, settings)
    if not job or job["status"] not in RETRYABLE | {"needs_ocr", "needs_review"}:
        raise APIError(409, "not_retryable", "This document cannot be reprocessed now")
    keep_stage = job["status"] in RETRYABLE and job.get("documentVersionId")

    def change(current):
        if current["status"] != job["status"]:
            raise APIError(409, "job_changed", "Processing state changed; reload")
        return {
            "status": "queued",
            "stage": current["stage"] if keep_stage else "parse",
            "failures": 0,
            "errorCode": None,
            "nextRunAt": utcnow(),
            "leaseOwner": None,
        }

    repo.mutate(
        "processing_jobs",
        job["id"],
        change,
        actor=user["id"],
        event="job.reprocess",
        request_id=request_id,
    )
    return processing(repo, document, settings)


def delete_document(repo, bucket, user, kb_id, doc_id, request_id, version):
    private_document(repo, user, kb_id, doc_id)
    result = documents.delete_document(
        repo,
        bucket,
        doc_id,
        user["id"],
        request_id,
        version,
        collection="knowledge_documents",
    )
    pipeline.cleanup_document(repo, bucket, doc_id, kb_id)
    return result


def review_provision(repo, provision_id, data, actor, request_id, version):
    def change(current):
        check_version(current, version)
        return {
            **data,
            "reviewState": "reviewed",
            "reviewedBy": actor,
            "sourceVerifiedAt": utcnow().isoformat(),
        }

    return repo.mutate(
        "provision_versions",
        provision_id,
        change,
        actor=actor,
        event="provision.review",
        request_id=request_id,
    )


def publish_generation(repo, kb_id, generation, version, actor, request_id, settings):
    """Admin switch of the serving generation; also used to roll back to a built one."""
    publication = repo.get("corpus_publications", f"{kb_id}-{generation}")
    if not publication:
        raise APIError(404, "not_found", "Generation not found")
    if publication["profileId"] != profile_from(settings).id:
        raise APIError(409, "profile_mismatch", "Generation uses another embedding profile")
    previous = {}

    def move(kb):
        check_version(kb, version)
        previous["generation"] = kb.get("activeIndexGeneration")
        return {"activeIndexGeneration": generation}

    kb = repo.mutate(
        "knowledge_bases", kb_id, move, actor=actor, event="kb.publish", request_id=request_id
    )
    if previous["generation"] and previous["generation"] != generation:
        mark_publication(repo, kb_id, previous["generation"], "superseded", actor, request_id)
    mark_publication(repo, kb_id, generation, "published", actor, request_id)
    approve_jobs(repo, kb_id, publication, actor, request_id)
    return kb_out(kb)


def mark_publication(repo, kb_id, generation, state, actor, request_id):
    repo.mutate(
        "corpus_publications",
        f"{kb_id}-{generation}",
        lambda current: {"state": state, "publishedAt": utcnow()} if current else None,
        actor=actor,
        event="publication." + state,
        request_id=request_id,
    )


def approve_jobs(repo, kb_id, publication, actor, request_id):
    """Jobs waiting for review whose generation is covered by the published one."""
    waiting = repo.query(
        "processing_jobs",
        [("kbId", "==", kb_id), ("status", "==", "needs_review")],
        limit=500,
    )
    for job in waiting:
        built = repo.get("corpus_publications", f"{kb_id}-{job['generationId']}")
        if built and built["createdAt"] <= publication["createdAt"]:
            repo.mutate(
                "processing_jobs",
                job["id"],
                lambda current: (
                    {"status": "succeeded"} if current["status"] == "needs_review" else None
                ),
                actor=actor,
                event="job.approved",
                request_id=request_id,
            )


def reconcile(repo, bucket, *, dry_run=True):
    """Expired uploads and deletions, plus chunks of generations that never got published."""
    results = documents.reconcile(
        repo,
        bucket,
        dry_run=dry_run,
        collection="knowledge_documents",
        prefix="knowledge-documents",
    )
    results["staleDerived"] = 0
    for kb in repo.scan("knowledge_bases"):
        known = {}
        for chunk in repo.scan("search_chunks", filters=[("kbId", "==", kb["id"])]):
            generation = chunk["indexGeneration"]
            if generation not in known:
                known[generation] = bool(
                    repo.get("corpus_publications", f"{kb['id']}-{generation}")
                )
            if known[generation] or generation.startswith("stage-"):
                continue
            results["staleDerived"] += 1
            if not dry_run:
                repo.remove("search_chunks", chunk["id"])
    return results
