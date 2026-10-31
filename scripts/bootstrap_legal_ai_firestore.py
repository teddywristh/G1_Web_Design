#!/usr/bin/env python3
"""Safely bootstrap Firestore schema marker documents.

Local demo projects use the Firestore Emulator and anonymous credentials.
Production projects use Application Default Credentials. The script is dry-run
by default and only creates missing ``_schema`` documents with ``--apply``.
It never updates or overwrites an existing document.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / "apps" / "api" / ".env")

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import AlreadyExists, GoogleAPICallError
from google.auth.credentials import AnonymousCredentials

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "demo-legal-ai")
SCHEMA_DOCUMENT_ID = "_schema"

COLLECTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "users": {
        "description": "User profiles and application-level roles.",
        "fields": {
            "uid": "string; Firebase Authentication UID",
            "email": "string",
            "display_name": "string",
            "role": "string; e.g. admin, lawyer, user",
            "status": "string; e.g. active, disabled",
            "created_at": "timestamp",
            "updated_at": "timestamp",
        },
    },
    "documents": {
        "description": "Legal source documents and their processing state.",
        "fields": {
            "document_id": "string",
            "title": "string",
            "document_type": "string; e.g. law, decree, circular",
            "storage_path": "string; Firebase Storage object path",
            "mime_type": "string",
            "file_size": "integer; bytes",
            "status": "string; e.g. uploaded, processing, ready, failed",
            "uploaded_by": "string; user UID",
            "created_at": "timestamp",
            "updated_at": "timestamp",
        },
    },
    "conversations": {
        "description": "Legal question-and-answer conversation sessions.",
        "fields": {
            "conversation_id": "string",
            "user_id": "string; Firebase Authentication UID",
            "title": "string",
            "created_at": "timestamp",
            "updated_at": "timestamp",
        },
    },
    "messages": {
        "description": "User prompts and assistant responses.",
        "fields": {
            "conversation_id": "string",
            "user_id": "string",
            "role": "string; user, assistant, or system",
            "content": "string",
            "sources": "array; retrieved legal source references",
            "created_at": "timestamp",
        },
    },
    "document_chunks": {
        "description": "Extracted text chunks and references to vector records.",
        "fields": {
            "document_id": "string",
            "chunk_index": "integer",
            "content": "string",
            "page_number": "integer; optional",
            "vector_id": "string; ID in the vector database",
            "created_at": "timestamp",
        },
    },
    "processing_jobs": {
        "description": "Document ingestion and processing job tracking.",
        "fields": {
            "document_id": "string",
            "status": "string; queued, running, completed, failed",
            "stage": "string; e.g. extraction, chunking, embedding",
            "error": "string or null",
            "created_at": "timestamp",
            "updated_at": "timestamp",
        },
    },
}


def _is_emulator() -> bool:
    return bool(os.getenv("FIRESTORE_EMULATOR_HOST"))


def get_firestore_client() -> firestore.Client:
    """Initialize Firestore without cloud credentials for the local demo."""
    if PROJECT_ID == "demo-legal-ai" and not _is_emulator():
        raise RuntimeError(
            "FIRESTORE_EMULATOR_HOST is required for demo-legal-ai; refusing cloud access"
        )

    try:
        app = firebase_admin.get_app()
    except ValueError:
        if _is_emulator():
            app = firebase_admin.initialize_app(
                credential=AnonymousCredentials(),
                options={"projectId": PROJECT_ID},
            )
        else:
            app = firebase_admin.initialize_app(
                credential=credentials.ApplicationDefault(),
                options={"projectId": PROJECT_ID},
            )

    if app.project_id != PROJECT_ID:
        raise RuntimeError(
            f"Project mismatch: expected {PROJECT_ID}, got {app.project_id}"
        )
    return firestore.client(app=app)


def bootstrap_collection(
    db: firestore.Client,
    collection_name: str,
    schema: dict[str, Any],
    apply: bool,
) -> str:
    collection_ref = db.collection(collection_name)
    schema_ref = collection_ref.document(SCHEMA_DOCUMENT_ID)

    if schema_ref.get().exists:
        return "SKIP: _schema already exists; no changes made"

    if list(collection_ref.limit(1).stream()):
        return "SKIP: collection contains data but has no _schema; inspect manually"

    payload = {
        "kind": "collection_schema",
        "collection": collection_name,
        "description": schema["description"],
        "fields": schema["fields"],
        "schema_version": 1,
        "managed_by": "legal-ai-firestore-bootstrap",
        "created_at": firestore.SERVER_TIMESTAMP,
    }

    if not apply:
        return "DRY RUN: would create _schema"

    try:
        schema_ref.create(payload)
        return "CREATED: _schema"
    except AlreadyExists:
        return "SKIP: _schema was created concurrently; no overwrite"
    except GoogleAPICallError as exc:
        return f"ERROR: Firestore API error: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Legal AI Firestore schema markers")
    parser.add_argument("--apply", action="store_true", help="Create missing _schema documents")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"Legal AI Firestore bootstrap | project={PROJECT_ID} | mode={mode}")
    print("No existing documents will be updated or overwritten.\n")

    try:
        db = get_firestore_client()
    except Exception as exc:
        print(f"ERROR: Could not initialize Firebase Admin: {exc}", file=sys.stderr)
        return 1

    results: list[tuple[str, str]] = []
    for name, schema in COLLECTION_SCHEMAS.items():
        try:
            status = bootstrap_collection(db, name, schema, args.apply)
        except Exception as exc:
            status = f"ERROR: {type(exc).__name__}: {exc}"
        results.append((name, status))
        print(f"[{name}] {status}")

    created = sum(status.startswith("CREATED") for _, status in results)
    skipped = sum(status.startswith("SKIP") for _, status in results)
    dry_run = sum(status.startswith("DRY RUN") for _, status in results)
    errors = sum(status.startswith("ERROR") for _, status in results)
    print(f"\nSummary\n  Created: {created}\n  Skipped: {skipped}\n  Would create: {dry_run}\n  Errors: {errors}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to create schema markers.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
