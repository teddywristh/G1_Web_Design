"""Replay scoring of recorded answers against a frozen gold manifest."""


def recall_at_k(required, retrieved, k):
    if not required:
        return 1.0
    return len(set(required) & set(retrieved[:k])) / len(set(required))


def score(cases, predictions, k=20):
    """cases: gold list; predictions: {case_id: AskResponse-like dict}. Reports counts, not claims."""
    rows = {"cases": 0, "status_correct": 0, "full_coverage": 0, "recall_sum": 0.0}
    rows.update(citation_total=0, citation_valid=0, isolation_leaks=0, missing=0)
    for case in cases:
        prediction = predictions.get(case["id"])
        if prediction is None:
            rows["missing"] += 1
            continue
        rows["cases"] += 1
        retrieved = [c["provision_version_id"] for c in prediction.get("citations", [])]
        retrieved += [c["id"] for c in prediction.get("retrieved_chunks", [])]
        rows["recall_sum"] += recall_at_k(case["required_evidence"], retrieved, k)
        if set(case["required_evidence"]) <= set(retrieved[:k]):
            rows["full_coverage"] += 1
        if prediction["status"] == case["expected_status"]:
            rows["status_correct"] += 1
        for citation in prediction.get("citations", []):
            rows["citation_total"] += 1
            valid = citation["provision_version_id"] in retrieved
            rows["citation_valid"] += valid
        forbidden = set(case.get("forbidden_evidence", []))
        rows["isolation_leaks"] += len(forbidden & set(retrieved))
    n = rows["cases"] or 1
    return {
        "cases": rows["cases"],
        "missingPredictions": rows["missing"],
        "statusAccuracy": rows["status_correct"] / n,
        "recallAtK": rows["recall_sum"] / n,
        "fullCoverage": rows["full_coverage"] / n,
        "citationResolvable": rows["citation_valid"] / (rows["citation_total"] or 1),
        "isolationLeaks": rows["isolation_leaks"],
    }
