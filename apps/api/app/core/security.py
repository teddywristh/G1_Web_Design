"""Firebase identity and server-owned profiles are the only authority."""

from typing import Any

from fastapi import Depends, Header, Request
from firebase_admin import auth

from app.core.errors import APIError
from app.core.firebase import initialize_firebase
from app.repositories.backend import BackendRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_sessions import authenticate


def get_repository():
    return BackendRepository(initialize_firebase()["db"])


def verify_firebase_token(
    authorization: str | None = Header(default=None),
    request: Request = None,
    repo=Depends(get_repository),
) -> dict[str, Any]:
    if not authorization and request is not None and request.cookies.get("legal_session"):
        session, profile = authenticate(repo, request)
        return {
            "uid": profile["id"],
            "_sessionId": session["id"],
            "_csrfToken": session["csrfToken"],
        }
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(401, "unauthenticated", "Bearer token required")
    token = authorization[7:].strip()
    if not token:
        raise APIError(401, "unauthenticated", "Bearer token required")
    initialize_firebase()
    try:
        return auth.verify_id_token(token, check_revoked=True)
    except (
        auth.InvalidIdTokenError,
        auth.ExpiredIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        auth.UserNotFoundError,
        ValueError,
    ) as exc:
        raise APIError(401, "unauthenticated", "Invalid or expired token") from exc


def require_admin(decoded_token: dict[str, Any], users: UserRepository) -> dict[str, Any]:
    uid = decoded_token.get("uid")
    profile = users.get(uid) if uid else None
    if not profile or profile.get("role") != "admin" or not profile.get("isActive"):
        raise APIError(403, "forbidden", "Admin permission required")
    return profile
