"""Durable ingestion worker: Firestore jobs, leases and fenced commits.

Run with: python -m app.workers.ingestion
"""

import json
import logging
import time
from datetime import timedelta
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.firebase import initialize_firebase
from app.ingestion import pipeline
from app.ingestion.validation import Cancelled, NeedsOCR, PermanentError
from app.repositories.backend import BackendRepository, utcnow
from app.services.ai import OpenAIService
from app.services.ai_connections import resolve

logger = logging.getLogger("legal_api")
CLAIMABLE = ["queued", "retry_wait", "running"]
STAGES = ["parse", "embed", "publish"]


class LostLease(Exception):
    pass


def claim(repo, settings, worker_id):
    """Take the oldest runnable job; running jobs become runnable again when the lease expires."""
    now = utcnow()
    rows = repo.query(
        "processing_jobs",
        [("status", "in", CLAIMABLE), ("nextRunAt", "<=", now)],
        order="nextRunAt",
        limit=5,
    )
    for row in rows:

        def take(current):
            if current["status"] not in CLAIMABLE or current["nextRunAt"] > now:
                return None
            until = now + timedelta(seconds=settings.job_lease_seconds)
            return {
                "status": "running",
                "leaseOwner": worker_id,
                "leaseUntil": until,
                "nextRunAt": until,
                "fence": current["fence"] + 1,
            }

        taken = repo.mutate(
            "processing_jobs",
            row["id"],
            take,
            actor=worker_id,
            event="job.claim",
            request_id=row["id"],
        )
        if taken["leaseOwner"] == worker_id and taken["fence"] == row["fence"] + 1:
            return taken
    return None


def commit(repo, settings, job, worker_id, patch, event="job.update"):
    """Write job state only while this worker still owns the lease."""

    def change(current):
        if not current or current["leaseOwner"] != worker_id or current["fence"] != job["fence"]:
            raise LostLease()
        return patch

    return repo.mutate(
        "processing_jobs", job["id"], change, actor=worker_id, event=event, request_id=job["id"]
    )


def heartbeat(repo, settings, job, worker_id):
    until = utcnow() + timedelta(seconds=settings.job_lease_seconds)
    commit(repo, settings, job, worker_id, {"leaseUntil": until, "nextRunAt": until})


def make_embedder(repo, settings, job):
    owner = repo.get("users", job["ownerUid"])
    if not owner or not owner.get("isActive"):
        raise APIError(503, "ai_not_configured", "Job owner is unavailable")
    credential = resolve(repo, owner, "openai", job["credentialSource"], settings)
    return OpenAIService(settings.model_copy(update={"openai_api_key": credential.api_key}))


def run_stage(repo, bucket, settings, job):
    if job["stage"] == "parse":
        return pipeline.parse_stage(repo, bucket, settings, job)
    if job["stage"] == "embed":
        return pipeline.embed_stage(repo, settings, job, make_embedder(repo, settings, job))
    return pipeline.publish_stage(repo, bucket, settings, job)


def process(repo, bucket, settings, job, worker_id):
    """Run the remaining stages; each stage result is committed under the lease."""
    try:
        while job["stage"] in STAGES:
            heartbeat(repo, settings, job, worker_id)
            result = run_stage(repo, bucket, settings, job)
            index = STAGES.index(job["stage"])
            patch = {"failures": 0, "errorCode": None}
            for key in ("documentVersionId", "quality", "warnings", "generationId"):
                if key in result:
                    patch[key] = result[key]
            if index + 1 < len(STAGES):
                patch["stage"] = STAGES[index + 1]
            else:
                shared = job["kbId"] == pipeline.SHARED_KB
                patch["status"] = "needs_review" if shared else "succeeded"
                patch["nextRunAt"] = None
                patch["leaseOwner"] = None
            job = commit(repo, settings, job, worker_id, patch)
            if job["status"] != "running":
                return job
    except LostLease:
        return None
    except Exception as exc:
        return fail(repo, settings, job, worker_id, exc)


def fail(repo, settings, job, worker_id, exc):
    end = {"nextRunAt": None, "leaseOwner": None}
    if isinstance(exc, Cancelled):
        patch = {"status": "cancelled", "errorCode": "source_unavailable", **end}
    elif isinstance(exc, NeedsOCR):
        patch = {"status": "needs_ocr", "errorCode": "needs_ocr", **end}
    elif isinstance(exc, PermanentError):
        patch = {"status": "failed", "errorCode": exc.code, **end}
    elif pipeline.is_auth_error(exc) or getattr(exc, "status_code", None) in (401, 403):
        patch = {"status": "needs_configuration", "errorCode": "ai_not_configured", **end}
    else:
        failures = job["failures"] + 1
        if failures >= settings.job_max_failures:
            patch = {"status": "failed", "errorCode": "retries_exhausted", "failures": failures}
            patch.update(end)
        else:
            patch = {
                "status": "retry_wait",
                "errorCode": "temporary_error",
                "failures": failures,
                "nextRunAt": pipeline.next_run(settings, failures),
                "leaseOwner": None,
            }
    logger.warning(
        json.dumps({"event": "job_failed", "jobId": job["id"], "type": type(exc).__name__})
    )
    try:
        return commit(repo, settings, job, worker_id, patch, event="job.failed")
    except LostLease:
        return None


def run_once(repo, bucket, settings, worker_id):
    job = claim(repo, settings, worker_id)
    if not job:
        return None
    return process(repo, bucket, settings, job, worker_id)


def main(poll_seconds=5):
    settings = get_settings()
    clients = initialize_firebase()
    repo = BackendRepository(clients["db"])
    worker_id = uuid4().hex
    while True:
        if run_once(repo, clients["storage"], settings, worker_id) is None:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
