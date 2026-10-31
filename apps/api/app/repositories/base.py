"""Small Firestore repository helpers shared by domain repositories."""

from typing import Any


class FirestoreRepository:
    def __init__(self, db: Any, collection_name: str):
        self.collection = db.collection(collection_name)

    def get(self, document_id: str) -> dict[str, Any] | None:
        snapshot = self.collection.document(document_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def create(self, document_id: str, data: dict[str, Any]) -> None:
        self.collection.document(document_id).create(data)

    def update(self, document_id: str, data: dict[str, Any]) -> None:
        self.collection.document(document_id).update(data)

    def delete(self, document_id: str) -> None:
        self.collection.document(document_id).delete()

    def list(self, *, limit: int = 20, start_after: Any = None) -> list[dict[str, Any]]:
        query = self.collection.limit(max(1, min(limit, 100)))
        if start_after is not None:
            query = query.start_after(start_after)
        return [{"id": item.id, **(item.to_dict() or {})} for item in query.stream()]
