"""Firestore database connection used by the RAG services."""

from typing import Any

from app.core.firebase import initialize_firebase


def get_database() -> Any:
    """Return the shared Firestore client."""
    return initialize_firebase()["db"]
