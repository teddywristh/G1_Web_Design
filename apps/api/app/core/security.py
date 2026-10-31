"""Authentication and server-side role checks."""

from typing import Any

from fastapi import Header, HTTPException, status
from firebase_admin import auth

from app.repositories.user_repository import UserRepository


def verify_firebase_token(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        return auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def require_admin(decoded_token: dict[str, Any], users: UserRepository) -> dict[str, Any]:
    uid = decoded_token.get("uid")
    profile = users.get(uid) if uid else None
    if not profile or profile.get("role") != "admin" or profile.get("isActive") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")
    return profile
