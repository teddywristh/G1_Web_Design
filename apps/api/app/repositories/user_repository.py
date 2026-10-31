from typing import Any

from app.repositories.base import FirestoreRepository


class UserRepository(FirestoreRepository):
    def __init__(self, db: Any):
        super().__init__(db, "users")
