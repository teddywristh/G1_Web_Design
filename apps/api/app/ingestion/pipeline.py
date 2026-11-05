import hashlib
import json
import logging
import math
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from app.core.errors import APIError
from app.ingestion import parser, segmenter, validation
from app.repositories.backend import utcnow
from app.search.base import profile_from
from app.services.documents import normalize
from app.services.users import check_version

PARSER_VERSION = "p4"
JOB_PARSER_VERSION = "p2"
CHUNKER_VERSION = "c2"
SHARED_KB = "shared"
logger = logging.getLogger("legal_api")


def job_id(kb_id, source_id, content_hash, profile_id):
    raw = "|".join(
        [kb_id, source_id, content_hash, JOB_PARSER_VERSION, CHUNKER_VERSION, profile_id]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def job_outbox(
    kb_id,
    collection,
    source_id,
    owner_uid,
    credential_source,
    settings,
    public_input_confirmed=False,
):
    """Rows written in the same transaction that marks the upload available."""
    profile = profile_from(settings)

    def rows(patch):
        key = job_id(kb_id, source_id, patch["sha256"], profile.id)
        job = {
            "kbId": kb_id,
            "sourceCollection": collection,
            "sourceId": source_id,
            "ownerUid": owner_uid,
            "credentialSource": credential_source,
            "publicEmbeddingInputConfirmed": public_input_confirmed,
            "sourceFence": {"sha256": patch["sha256"], "storagePath": patch["storagePath"]},
            "embeddingProfileId": profile.id,
            "stage": "parse",
            "status": "queued",
            "fence": 0,
            "failures": 0,
            "leaseOwner": None,
            "leaseUntil": None,
            "nextRunAt": utcnow(),
            "errorCode": None,
            "documentVersionId": None,
            "generationId": None,
            "warnings": [],
            "quality": {},
            "version": 1,
        }
        return [("processing_jobs", key, job)]

    return rows


def usable_source(repo, job):
    """Tombstone and source-fence check; raises Cancelled when the source moved on."""
    source = repo.get(job["sourceCollection"], job["sourceId"])
    fence = job["sourceFence"]
    if (
        not source
        or source.get("deletedAt") is not None
        or source.get("fileState") != "available"
        or source.get("sha256") != fence["sha256"]
        or source.get("storagePath") != fence["storagePath"]
    ):
        raise validation.Cancelled()
    return source


def validity_fields(source, shared):
    """Admin metadata is a reviewed source; user uploads stay unverified."""
    base = {
        "validFrom": None,
        "validUntil": None,
        "endKind": "unknown",
        "validityReviewState": "unknown",
        "applicabilityNotes": "",
        "legalStatus": "unknown",
        "sourceVerifiedAt": None,
        "relationRefs": [],
        "reviewState": "unreviewed",
    }
    if not shared:
        return base
    status = source.get("status")
    base.update(legalStatus=status, validFrom=source.get("effectiveDate"), reviewState="reviewed")
    if status in {"effective", "not_yet_effective"}:
        base.update(endKind="open", validityReviewState="reviewed")
    return base


REVIEW_FIELDS = (
    "validFrom",
    "validUntil",
    "endKind",
    "validityReviewState",
    "applicabilityNotes",
    "sourceVerifiedAt",
    "relationRefs",
    "reviewState",
    "reviewedBy",
)


def kept_review(old):
    """A human review survives re-parsing of the same file."""
    return {key: old[key] for key in REVIEW_FIELDS if key in old} if old else {}


def parse_stage(repo, bucket, settings, job, heartbeat=None):
    source = usable_source(repo, job)
    shared = job["kbId"] == SHARED_KB
    # Đóng file trước khi parser mở lại để chạy được trên Windows.
    with TemporaryDirectory(prefix="legal-ingestion-") as directory:
        path = str(Path(directory) / "source.pdf")
        blob = bucket.blob(source["storagePath"])
        blob.download_to_filename(path, timeout=settings.storage_timeout_seconds, retry=None)
        with open(path, "rb") as saved:
            if hashlib.sha256(saved.read()).hexdigest() != job["sourceFence"]["sha256"]:
                raise validation.Cancelled()
        pages = parser.extract_pages(path, settings.max_pdf_pages, settings, heartbeat)
    quality = validation.check_pages(pages, False)
    provisions = segmenter.segment(pages, settings.max_provision_chars)
    warnings = validation.check_structure(provisions)
    version_id = f"{job['sourceId']}-{job['sourceFence']['sha256'][:16]}-{PARSER_VERSION}"
    artifact = f"knowledge-artifacts/{job['kbId']}/{version_id}/pages.json"
    bucket.blob(artifact).upload_from_string(
        json.dumps(pages, ensure_ascii=False), content_type="application/json"
    )
    title = source.get("title") or source.get("displayTitle") or ""
    number = source.get("documentNumber") or ""
    repo.put(
        "document_versions",
        version_id,
        {
            "sourceCollection": job["sourceCollection"],
            "sourceId": job["sourceId"],
            "kbId": job["kbId"],
            "contentHash": job["sourceFence"]["sha256"],
            "parserVersion": PARSER_VERSION,
            "chunkerVersion": CHUNKER_VERSION,
            "extractedTextRef": artifact,
            "quality": quality,
            "createdAt": utcnow(),
        },
    )
    reviewed = {
        row["id"]: row
        for row in repo.query(
            "provision_versions", [("documentVersionId", "==", version_id)], limit=20000
        )
        if row.get("reviewedBy")
    }
    rows = {}
    for index, item in enumerate(provisions):
        row_id = f"{version_id}-{index:05d}"
        rows[row_id] = {
            **item,
            **validity_fields(source, shared),
            **kept_review(reviewed.get(row_id)),
            "version": 1,
            "createdAt": utcnow(),
            "updatedAt": utcnow(),
            "documentVersionId": version_id,
            "kbId": job["kbId"],
            "sourceCollection": job["sourceCollection"],
            "sourceId": job["sourceId"],
            "documentTitle": title,
            "documentNumber": number,
            "documentNumberNormalized": normalize(number),
            "sourceType": "official_legal_text" if shared else "user_document",
            "sourceUrl": source.get("sourceUrl"),
            "jurisdiction": "VN",
            "derived": False,
        }
    repo.put_many("provision_versions", rows)
    return {
        "documentVersionId": version_id,
        "quality": quality,
        "warnings": warnings,
        "provisionCount": len(rows),
    }


def search_text(row):
    path = [row["documentTitle"], row["chapter"] and "Chương " + row["chapter"]]
    path += [row["article"], row["clause"]]
    return " | ".join(item for item in path if item) + "\n" + row["text"]


def staged_generation(version_id):
    return "stage-" + version_id


def embed_stage(repo, settings, job, embedder, heartbeat=None, progress=None):
    usable_source(repo, job)
    profile = profile_from(settings)
    if job["embeddingProfileId"] != profile.id:
        raise validation.PermanentError("embedding_profile_changed")
    version_id = job["documentVersionId"]
    provisions = list(
        repo.scan("provision_versions", filters=[("documentVersionId", "==", version_id)])
    )
    provisions.sort(key=lambda row: row["id"])
    total = len(provisions)
    scope = hashlib.sha256(f"{version_id}|{profile.id}|full".encode()).hexdigest()[:40]
    stage = "stage-" + scope
    existing = {
        row["provisionVersionId"]
        for row in repo.scan("search_chunks", filters=[("indexGeneration", "==", stage)])
    }
    indexed = len(provisions)
    completed = sum(row["id"] in existing for row in provisions)
    if progress:
        progress(completed, indexed)
    batch_size = (
        1
        if settings.embedding_provider == "openrouter"
        and settings.openrouter_embedding_model.endswith(":free")
        else settings.embedding_batch_size
    )
    for start in range(0, len(provisions), batch_size):
        if heartbeat:
            heartbeat()
        batch = [row for row in provisions[start : start + batch_size] if row["id"] not in existing]
        if not batch:
            continue
        vectors = embedder.embed([search_text(row) for row in batch])
        if len(vectors) != len(batch):
            raise validation.PermanentError("embedding_count_mismatch")
        chunks = {}
        for row, vector in zip(batch, vectors):
            if len(vector) != profile.dimensions or not all(math.isfinite(x) for x in vector):
                raise validation.PermanentError("embedding_invalid")
            chunks[f"{stage}-{row['id']}"] = {
                "kbId": job["kbId"],
                "indexGeneration": stage,
                "documentVersionId": version_id,
                "provisionVersionId": row["id"],
                "documentId": row["sourceId"],
                "sourceCollection": row["sourceCollection"],
                "parentId": f"{version_id}:{row['articleNo']}" if row["articleNo"] else None,
                "searchText": search_text(row),
                "vector": list(vector),
                "embeddingProfileId": profile.id,
                "state": "active",
            }
        if heartbeat:
            heartbeat()
        repo.put_many("search_chunks", chunks)
        completed += len(batch)
        if progress:
            progress(completed, indexed)
        logger.info(
            json.dumps(
                {
                    "event": "embedding_progress",
                    "jobId": job["id"],
                    "completed": start + len(provisions[start : start + batch_size]),
                    "total": indexed,
                }
            )
        )
    return {
        "chunkCount": indexed,
        "stagingGeneration": stage,
        "embeddingCoverage": {
            "total": total,
            "indexed": indexed,
            "start": 1 if total else 0,
        },
    }


def alive_documents(repo, chunks):
    """Document ids in chunks whose source is still available."""
    alive = {}
    for chunk in chunks:
        key = chunk["documentId"]
        if key not in alive:
            source = repo.get(chunk["sourceCollection"], key)
            alive[key] = bool(
                source
                and source.get("deletedAt") is None
                and source.get("fileState") == "available"
            )
    return alive


def regenerate(chunk, generation):
    row = {key: value for key, value in chunk.items() if key != "id"}
    return {**row, "indexGeneration": generation}


def publish_stage(repo, bucket, settings, job):
    """Build a complete new generation, then move the pointer with a version check."""
    source = usable_source(repo, job)
    kb = repo.get("knowledge_bases", job["kbId"])
    if not kb or kb.get("deletedAt") is not None:
        raise validation.Cancelled()
    version_id = job["documentVersionId"]
    stage = job.get("stagingGeneration") or staged_generation(version_id)
    latest = kb.get("latestGeneration")
    carried = []
    if latest:
        carried = list(
            repo.scan(
                "search_chunks",
                filters=[("kbId", "==", kb["id"]), ("indexGeneration", "==", latest)],
            )
        )
    alive = alive_documents(repo, carried)
    if any(
        alive[chunk["documentId"]]
        and chunk["documentId"] != source["id"]
        and chunk.get("embeddingProfileId") != job["embeddingProfileId"]
        for chunk in carried
    ):
        raise validation.PermanentError("embedding_profile_changed")
    new_generation = uuid4().hex
    rows = {}
    for chunk in carried:
        if alive[chunk["documentId"]] and chunk["documentId"] != source["id"]:
            rows[f"{new_generation}-{chunk['provisionVersionId']}"] = regenerate(
                chunk, new_generation
            )
    staged = list(repo.scan("search_chunks", filters=[("indexGeneration", "==", stage)]))
    for chunk in staged:
        rows[f"{new_generation}-{chunk['provisionVersionId']}"] = regenerate(chunk, new_generation)
    if not staged:
        raise validation.PermanentError("no_chunks")
    repo.put_many("search_chunks", rows)
    document_ids = sorted({chunk["documentId"] for chunk in rows.values()})
    manifest = f"knowledge-manifests/{kb['id']}/{new_generation}.json"
    bucket.blob(manifest).upload_from_string(
        json.dumps({"documentIds": document_ids, "chunkCount": len(rows)}),
        content_type="application/json",
    )
    private = kb["kind"] == "private"
    repo.put(
        "corpus_publications",
        f"{kb['id']}-{new_generation}",
        {
            "kbId": kb["id"],
            "generationId": new_generation,
            "state": "published" if private else "built",
            "manifestRef": manifest,
            "profileId": job["embeddingProfileId"],
            "createdAt": utcnow(),
            "publishedAt": utcnow() if private else None,
        },
    )

    def move(current):
        check_version(current, kb["version"])
        patch = {
            "latestGeneration": new_generation,
            "embeddingProfileId": job["embeddingProfileId"],
        }
        if private:
            patch["activeIndexGeneration"] = new_generation
        return patch

    repo.mutate(
        "knowledge_bases",
        kb["id"],
        move,
        actor="worker",
        event="knowledge.generation_built",
        request_id=job["id"],
    )
    for chunk_id in [f"{stage}-{chunk['provisionVersionId']}" for chunk in staged]:
        repo.remove("search_chunks", chunk_id)
    return {"generationId": new_generation, "published": private}


def cleanup_document(repo, bucket, source_id, kb_id):
    """Remove derived data of a deleted source. Retrieval is already blocked by the tombstone."""
    for collection in ("search_chunks", "provision_versions", "document_versions"):
        field = "documentId" if collection == "search_chunks" else "sourceId"
        while True:
            rows = repo.query(collection, [(field, "==", source_id)], limit=400)
            for row in rows:
                repo.remove(collection, row["id"])
            if len(rows) < 400:
                break
    for blob in bucket.list_blobs(prefix=f"knowledge-artifacts/{kb_id}/{source_id}-"):
        blob.delete()


def next_run(settings, failures):
    return utcnow() + timedelta(seconds=settings.job_backoff_seconds * 2**failures)


def is_auth_error(exc):
    return isinstance(exc, APIError) and exc.code in {
        "ai_not_configured",
        "ai_authentication_failed",
    }
