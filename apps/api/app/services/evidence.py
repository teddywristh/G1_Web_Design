from datetime import date

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


def validate(repo, candidate, allowed, as_of, cache):
    """Re-read canonical records; index copies are never trusted."""
    provision = repo.get("provision_versions", candidate["provisionVersionId"])
    if not provision or provision["kbId"] not in allowed:
        return None
    if not source_alive(repo, provision, cache):
        return None
    chunk = repo.get("search_chunks", f"{candidate['generation']}-{provision['id']}")
    if not chunk or chunk.get("state") != "active":
        return None
    usable, limits = applicability.check(provision, as_of)
    return to_item(provision, candidate, limits) if usable else None


def build(repo, candidates, allowed, as_of, limit):
    cache, items = {}, []
    for candidate in candidates:
        item = validate(repo, candidate, allowed, as_of, cache)
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def expand(repo, items, allowed, as_of, limit):
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
            related = validate(repo, candidate, allowed, as_of, cache)
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
    if not generation or not source_alive(repo, provision, {}):
        raise APIError(404, "not_found", "Evidence not found")
    if not repo.get("search_chunks", f"{generation}-{provision_id}"):
        raise APIError(404, "not_found", "Evidence not found")
    _, limits = applicability.check(provision, date.today())
    return {
        **to_item(provision, {}, limits),
        "id": provision_id,
        "validFrom": provision.get("validFrom"),
        "validUntil": provision.get("validUntil"),
        "endKind": provision.get("endKind", "unknown"),
        "validityReviewState": provision.get("validityReviewState", "unknown"),
    }
