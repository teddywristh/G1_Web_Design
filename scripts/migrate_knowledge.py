#!/usr/bin/env python3
"""Move existing admin documents into the shared knowledge base. Dry-run by default.

Legacy document_chunks and sample/_schema records are quarantined, never served.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))

from app.core.config import get_settings
from app.core.firebase import initialize_firebase
from app.ingestion import pipeline
from app.repositories.backend import BackendRepository
from app.services import knowledge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", required=True, help="Must match FIREBASE_PROJECT_ID"
    )
    parser.add_argument("--apply", action="store_true", help="Persist changes")
    args = parser.parse_args()
    settings = get_settings()
    if args.project != settings.firebase_project_id:
        parser.error("--project does not match runtime configuration")
    repo = BackendRepository(initialize_firebase()["db"])
    report = {
        "dryRun": not args.apply,
        "queued": 0,
        "skipped": 0,
        "quarantinedChunks": 0,
    }
    if args.apply:
        knowledge.ensure_shared_kb(repo, "migration")
    for document in repo.scan("legal_documents"):
        ready = (
            document.get("fileState") == "available"
            and document.get("deletedAt") is None
        )
        if not ready or "_schema" in document or document.get("sample"):
            report["skipped"] += 1
            continue
        report["queued"] += 1
        if args.apply:
            outbox = pipeline.job_outbox(
                knowledge.SHARED,
                "legal_documents",
                document["id"],
                document["createdBy"],
                "auto",
                settings,
            )
            for name, doc_id, data in outbox(document):
                repo.put(name, doc_id, {**data, "createdAt": document["createdAt"]})
    for chunk in repo.scan("document_chunks"):
        report["quarantinedChunks"] += 1
        if args.apply and not chunk.get("quarantined"):
            repo.put("document_chunks", chunk["id"], {**chunk, "quarantined": True})
    print(json.dumps(report))


if __name__ == "__main__":
    main()
