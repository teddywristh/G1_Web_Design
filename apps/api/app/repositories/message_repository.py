from typing import Any


class MessageRepository:
    def __init__(self, db: Any):
        self.db = db

    def _collection(self, conversation_id: str):
        return self.db.collection("conversations").document(conversation_id).collection("messages")

    def create(self, conversation_id: str, message_id: str, data: dict[str, Any]) -> None:
        self._collection(conversation_id).document(message_id).create(data)

    def get(self, conversation_id: str, message_id: str) -> dict[str, Any] | None:
        snapshot = self._collection(conversation_id).document(message_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def list(self, conversation_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return [{"id": item.id, **(item.to_dict() or {})} for item in self._collection(conversation_id).order_by("createdAt").limit(limit).stream()]
