from typing import Any

from app.repositories.base import FirestoreRepository


class ConversationRepository(FirestoreRepository):
    def __init__(self, db: Any):
        super().__init__(db, "conversations")

    def list_for_user(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return [{"id": item.id, **(item.to_dict() or {})} for item in self.collection.where("userId", "==", user_id).order_by("updatedAt", direction="DESCENDING").limit(limit).stream()]
