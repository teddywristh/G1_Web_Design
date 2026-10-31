from typing import Any

from app.repositories.base import FirestoreRepository


class DocumentRepository(FirestoreRepository):
    def __init__(self, db: Any):
        super().__init__(db, "legal_documents")

    def list_by_status(self, status: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return [{"id": item.id, **(item.to_dict() or {})} for item in self.collection.where("status", "==", status).limit(limit).stream()]
