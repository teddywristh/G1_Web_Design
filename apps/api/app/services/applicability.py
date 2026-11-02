def check(provision, as_of):
    """Select by legal time. Returns (usable, limitations); it does not resolve transitions."""
    day = as_of.isoformat()
    if provision.get("validFrom") and day < provision["validFrom"]:
        return False, []
    if provision.get("endKind") == "known_end" and provision.get("validUntil"):
        if day > provision["validUntil"]:
            return False, []
    limits = []
    if provision.get("validityReviewState") != "reviewed":
        limits.append("validity_unverified")
    if provision.get("validityReviewState") == "conflict":
        limits.append("validity_conflict")
    if provision.get("legalStatus") == "expired" and provision.get("endKind") != "known_end":
        limits.append("expired_end_date_unknown")
    if provision.get("legalStatus") == "partially_expired":
        limits.append("partially_expired")
    if provision.get("sourceType") == "user_document":
        limits.append("user_document_unverified")
    return True, limits
