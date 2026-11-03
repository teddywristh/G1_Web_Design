from datetime import date

from app.core.config import get_settings
from app.core.errors import APIError
from app.services import applicability, knowledge


def source_alive(repo, provision, cache):
    key = (provision["sourceCollection"], provision["sourceId"])
    if key not in cache:
        source = repo.get(*key)
        cache[key] = bool(
            source and source.get("deletedAt") is None and source.get("fileState") == "available"
        )
    return cache[key]


def to_item(provision, candidate, limits):
    return {
        "provisionVersionId": provision["id"],
        "kbId": provision["kbId"],
        "documentId": provision["sourceId"],
        "documentVersionId": provision["documentVersionId"],
        "title": provision["documentTitle"],
        "number": provision["documentNumber"],
        "identifier": provision["identifier"],
        "articleNo": provision.get("articleNo"),
        "generation": candidate.get("generation"),
        "chapter": provision.get("chapter"),
        "article": provision.get("article"),
        "clause": provision.get("clause"),
        "text": provision["text"],
        "pageStart": provision["pageStart"],
        "pageEnd": provision["pageEnd"],
        "sourceType": provision["sourceType"],
        "sourceUrl": provision.get("sourceUrl"),
        "limitations": limits,
        "score": candidate.get("score", 0.0),
        "via": candidate.get("via", "related"),
    }


def pending_provision(repo, provision, settings):
    if provision.get("sourceCollection") != "knowledge_documents":
        return False
    source = repo.get("knowledge_documents", provision["sourceId"])
    if (
        not source
        or source.get("kbId") != provision.get("kbId")
        or source.get("deletedAt") is not None
        or source.get("fileState") != "available"
    ):
        return False
    job = knowledge.find_job(repo, source, settings)
    return bool(
        job
        and job.get("documentVersionId") == provision.get("documentVersionId")
        and job.get("stage") in {"embed", "publish"}
        and job.get("status")
        in {"queued", "running", "retry_wait", "failed", "needs_configuration"}
        and job.get("sourceFence", {}).get("sha256") == source.get("sha256")
        and job.get("sourceFence", {}).get("storagePath") == source.get("storagePath")
    )


def validate(repo, candidate, allowed, as_of, cache, settings):
    """Re-read canonical records; index copies are never trusted."""
    provision = repo.get("provision_versions", candidate["provisionVersionId"])
    if not provision or provision["kbId"] not in allowed:
        return None
    if not source_alive(repo, provision, cache):
        return None
    generation = candidate.get("generation")
    chunk = repo.get("search_chunks", f"{generation}-{provision['id']}") if generation else None
    pending = not chunk or chunk.get("state") != "active"
    if pending and not pending_provision(repo, provision, settings):
        return None
    usable, limits = applicability.check(provision, as_of)
    if pending:
        limits.append("document_processing")
    return to_item(provision, candidate, limits) if usable else None


def build(repo, candidates, allowed, as_of, limit, settings):
    cache, items = {}, []
    for candidate in candidates:
        item = validate(repo, candidate, allowed, as_of, cache, settings)
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def expand(repo, items, allowed, as_of, limit, settings):
    """Sibling provisions of the same article, then reviewed relations; bounded by limit."""
    cache, known = {}, {item["provisionVersionId"] for item in items}
    extra = []
    for item in items:
        if len(extra) >= limit:
            break
        if not item["articleNo"]:
            continue
        siblings = repo.query(
            "provision_versions",
            [
                ("documentVersionId", "==", item["documentVersionId"]),
                ("articleNo", "==", item["articleNo"]),
            ],
            limit=50,
        )
        for row in sorted(siblings, key=lambda r: r["id"]):
            if row["id"] in known or len(extra) >= limit:
                continue
            candidate = {"provisionVersionId": row["id"], "generation": item["generation"]}
            related = validate(repo, candidate, allowed, as_of, cache, settings)
            if related:
                known.add(row["id"])
                extra.append(related)
    return items + extra


def read(repo, user, provision_id):
    """Source viewer: current permission, tombstone and publication are all re-checked."""
    provision = repo.get("provision_versions", provision_id)
    if not provision:
        raise APIError(404, "not_found", "Evidence not found")
    kb = knowledge.kb_for_user(repo, user, provision["kbId"])
    generation = kb.get("activeIndexGeneration")
    if not source_alive(repo, provision, {}):
        raise APIError(404, "not_found", "Evidence not found")
    published = generation and repo.get("search_chunks", f"{generation}-{provision_id}")
    pending = not published and pending_provision(repo, provision, get_settings())
    if not published and not pending:
        raise APIError(404, "not_found", "Evidence not found")
    _, limits = applicability.check(provision, date.today())
    if pending:
        limits.append("document_processing")
    return {
        **to_item(provision, {}, limits),
        "id": provision_id,
        "documentTitle": provision["documentTitle"],
        "documentNumber": provision["documentNumber"],
        "validFrom": provision.get("validFrom"),
        "validUntil": provision.get("validUntil"),
        "endKind": provision.get("endKind", "unknown"),
        "validityReviewState": provision.get("validityReviewState", "unknown"),
    }
