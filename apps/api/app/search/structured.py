import re

from app.services.documents import normalize


def parse_reference(query):
    """Extract document number, article, clause from a question."""
    text = normalize(query)
    number = re.search(r"\b\d{1,4}/\d{4}/[a-z0-9\-]+", text)
    article = re.search(r"\bdieu\s+(\d+)", text)
    clause = re.search(r"\bkhoan\s+(\d+)", text)
    return {
        "number": number.group(0) if number else None,
        "article": article.group(1) if article else None,
        "clause": clause.group(1) if clause else None,
    }


def search(repo, request):
    """Exact lookup by identifier inside each authorized knowledge base."""
    ref = parse_reference(request.query)
    if not ref["article"]:
        return []
    found = []
    for kb in request.kbs:
        filters = [("kbId", "==", kb["id"]), ("articleNo", "==", ref["article"])]
        if ref["number"]:
            filters.append(("documentNumberNormalized", "==", ref["number"]))
        if ref["clause"]:
            filters.append(("clauseNo", "==", ref["clause"]))
        for row in repo.query("provision_versions", filters, limit=request.candidate_k):
            found.append(
                {
                    "provisionVersionId": row["id"],
                    "kbId": kb["id"],
                    "generation": kb["generation"],
                    "score": 1.0,
                    "via": "exact",
                }
            )
    return found
