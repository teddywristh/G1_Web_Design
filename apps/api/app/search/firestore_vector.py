def search(repo, request):
    """Indexed nearest-neighbour query per (KB, generation) pair."""
    found = []
    for kb in request.kbs:
        filters = [
            ("kbId", "==", kb["id"]),
            ("indexGeneration", "==", kb["generation"]),
            ("embeddingProfileId", "==", request.profile.id),
            ("state", "==", "active"),
        ]
        for row in repo.nearest("search_chunks", filters, request.vector, request.candidate_k):
            found.append(
                {
                    "provisionVersionId": row["provisionVersionId"],
                    "kbId": kb["id"],
                    "generation": kb["generation"],
                    "score": 1 - row["distance"],
                    "via": "semantic",
                }
            )
    found.sort(key=lambda item: item["score"], reverse=True)
    return found[: request.candidate_k]


def merge(exact, semantic):
    """Exact hits first; duplicates collapse on the canonical provision."""
    merged, seen = [], set()
    for item in exact + semantic:
        if item["provisionVersionId"] not in seen:
            seen.add(item["provisionVersionId"])
            merged.append(item)
    return merged
