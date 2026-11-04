"""Read-only retrieval evaluation against the live Firestore index.

Runs the same code as POST /rag/ask up to the evidence list:
query embedding -> exact lookup + Firestore vector search -> merge -> re-validation.
It never writes to Firestore. Recall@k counts a question as a hit when one of the
first k validated results belongs to a gold article.

Usage (from the repository root, with the cloud settings exported):
    python experiments/retrieval/run_retrieval_eval.py KB_ID
"""

import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.core.firebase import initialize_firebase
from app.repositories.backend import BackendRepository
from app.search import firestore_vector, structured
from app.search.base import SearchRequest, profile_from
from app.services import evidence
from app.services.embeddings import LocalEmbedding

HERE = Path(__file__).resolve().parent
TOP = 10


def main(kb_id):
    settings = get_settings()
    repo = BackendRepository(initialize_firebase()["db"])
    kb = repo.get("knowledge_bases", kb_id)
    generation = kb["activeIndexGeneration"]
    profile = profile_from(settings)
    assert kb.get("embeddingProfileId") == profile.id, "index was built with another profile"
    kbs = [{"id": kb_id, "generation": generation}]
    allowed = {kb_id}
    as_of = date.today()
    embedder = LocalEmbedding(settings, input_type="query")
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["questions"]

    # Warm-up: first Firestore and model calls include connection setup.
    vector = embedder.embed(["khởi động"])[0]
    firestore_vector.search(
        repo, SearchRequest("x", kbs, as_of, profile, vector, settings.candidate_k)
    )

    rows = []
    for item in questions:
        t0 = time.perf_counter()
        vector = embedder.embed([item["q"]])[0]
        t1 = time.perf_counter()
        request = SearchRequest(item["q"], kbs, as_of, profile, vector, settings.candidate_k)
        exact = structured.search(repo, request)
        t2 = time.perf_counter()
        semantic = firestore_vector.search(repo, request)
        t3 = time.perf_counter()
        merged = firestore_vector.merge(exact, semantic)
        found = evidence.build(repo, merged, allowed, as_of, TOP, settings)
        t4 = time.perf_counter()
        articles = [x["articleNo"] for x in found]
        ranks = [n for n, a in enumerate(articles, 1) if a in item["gold"]]
        rows.append(
            {
                **item,
                "reference": structured.parse_reference(item["q"]),
                "exactHits": len(exact),
                "top": [
                    {"article": x["articleNo"], "clause": x["clause"], "via": x["via"],
                     "score": round(x["score"], 4)}
                    for x in found
                ],
                "firstGoldRank": ranks[0] if ranks else None,
                "ms": {
                    "embed": (t1 - t0) * 1000,
                    "exact": (t2 - t1) * 1000,
                    "vector": (t3 - t2) * 1000,
                    "revalidate": (t4 - t3) * 1000,
                    "total": (t4 - t0) * 1000,
                },
            }
        )
        print(item["id"], ranks[:1], articles[:5], round((t4 - t0) * 1000))

    def summary(subset):
        n = len(subset)
        rank = [r["firstGoldRank"] for r in subset]
        ms = lambda key: statistics.mean(r["ms"][key] for r in subset)  # noqa: E731
        return {
            "questions": n,
            "recall@1": sum(1 for x in rank if x and x <= 1) / n,
            "recall@5": sum(1 for x in rank if x and x <= 5) / n,
            "recall@10": sum(1 for x in rank if x and x <= 10) / n,
            "mrr@10": sum(1 / x for x in rank if x) / n,
            "avg_ms": {k: ms(k) for k in ("embed", "exact", "vector", "revalidate", "total")},
            "median_total_ms": statistics.median(r["ms"]["total"] for r in subset),
        }

    result = {
        "date": as_of.isoformat(),
        "kb": kb_id,
        "generation": generation,
        "profile": profile.id,
        "candidate_k": settings.candidate_k,
        "summary": {
            "exact": summary([r for r in rows if r["type"] == "exact"]),
            "natural": summary([r for r in rows if r["type"] == "natural"]),
            "all": summary(rows),
        },
        "rows": rows,
    }
    (HERE / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(result["summary"], indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
