from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app.core.config import get_settings
from app.core.errors import APIError
from app.services import applicability, knowledge

PREFETCH_WINDOW = 16
QUERY_WORKERS = 8


class ReadCache:
    """Per-request read-through cache over a repository.

    Validating one candidate takes several dependent reads. prefetch() turns the reads of many
    candidates into a few batched round trips; get() then answers from memory. Nothing is shared
    across requests, so canonical records are still re-read on every question.
    """

    def __init__(self, repo):
        self.repo = repo
        self.rows = {}

    def get(self, collection, doc_id):
        key = (collection, doc_id)
        if key not in self.rows:
            self.rows[key] = self.repo.get(collection, doc_id)
        return self.rows[key]

    def prefetch(self, collection, doc_ids):
        missing = [i for i in dict.fromkeys(doc_ids) if i and (collection, i) not in self.rows]
        if not missing:
            return
        many = getattr(self.repo, "get_many", None)
        found = many(collection, missing) if many else {}
        for doc_id in missing:
            # Without a batch API, leave the key unset so get() reads it on demand.
            if many:
                self.rows[(collection, doc_id)] = found.get(doc_id)

    def seed(self, collection, row):
        self.rows[(collection, row["id"])] = row

    def __getattr__(self, name):
        if name in {"repo", "rows"}:
            raise AttributeError(name)
        return getattr(self.repo, name)


def cached(repo):
    return repo if isinstance(repo, ReadCache) else ReadCache(repo)


def prefetch(cache, candidates):
    """Warm every record validate() will read for these candidates in three batched reads."""
    cache.prefetch("provision_versions", [c["provisionVersionId"] for c in candidates])
    sources = {}
    for candidate in candidates:
        provision = cache.rows.get(("provision_versions", candidate["provisionVersionId"]))
        if provision:
            sources.setdefault(provision["sourceCollection"], []).append(provision["sourceId"])
    for collection, ids in sources.items():
        cache.prefetch(collection, ids)
    cache.prefetch(
        "search_chunks",
        [
            f"{c['generation']}-{c['provisionVersionId']}"
            for c in candidates
            if c.get("generation") and c["provisionVersionId"]
        ],
    )


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
    reads, cache, items = cached(repo), {}, []
    for start in range(0, len(candidates), PREFETCH_WINDOW):
        window = candidates[start : start + PREFETCH_WINDOW]
        prefetch(reads, window)
        for candidate in window:
            item = validate(reads, candidate, allowed, as_of, cache, settings)
            if item:
                items.append(item)
            if len(items) >= limit:
                return items
    return items


def expand(repo, items, allowed, as_of, limit, settings):
    """Sibling provisions of the same article, then reviewed relations; bounded by limit."""
    reads, cache, known = cached(repo), {}, {item["provisionVersionId"] for item in items}
    # One query per distinct article (several clauses of one article share their siblings),
    # issued concurrently; the walk below stays in item order so the result is deterministic.
    wanted = list(
        dict.fromkeys(
            (item["documentVersionId"], item["articleNo"]) for item in items if item["articleNo"]
        )
    )

    def siblings_of(key):
        return reads.query(
            "provision_versions",
            [("documentVersionId", "==", key[0]), ("articleNo", "==", key[1])],
            limit=50,
        )

    if len(wanted) > 1:
        with ThreadPoolExecutor(max_workers=min(QUERY_WORKERS, len(wanted))) as pool:
            found = dict(zip(wanted, pool.map(siblings_of, wanted)))
    else:
        found = {key: siblings_of(key) for key in wanted}
    candidates = []
    for item in items:
        for row in found.get((item["documentVersionId"], item["articleNo"]), []):
            reads.seed("provision_versions", row)  # same collection validate() would re-read
            if row["id"] not in known:
                candidates.append(
                    {"provisionVersionId": row["id"], "generation": item["generation"]}
                )
    prefetch(reads, candidates)
    extra = []
    for item in items:
        if len(extra) >= limit:
            break
        if not item["articleNo"]:
            continue
        siblings = found[(item["documentVersionId"], item["articleNo"])]
        for row in sorted(siblings, key=lambda r: r["id"]):
            if row["id"] in known or len(extra) >= limit:
                continue
            candidate = {"provisionVersionId": row["id"], "generation": item["generation"]}
            related = validate(reads, candidate, allowed, as_of, cache, settings)
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
