from fastapi import Depends, Header

from app.core.errors import APIError
from app.core.firebase import initialize_firebase
from app.core.security import get_repository, verify_firebase_token


def get_bucket():
    return initialize_firebase()["storage"]


def current_user(token=Depends(verify_firebase_token), repo=Depends(get_repository)):
    uid = token.get("uid")
    user = repo.get("users", uid) if uid else None
    if not user:
        raise APIError(403, "profile_required", "Bootstrap your profile first")
    if not user.get("isActive"):
        raise APIError(403, "account_disabled", "Account is disabled")
    return user


def admin_user(user=Depends(current_user)):
    if user.get("role") != "admin":
        raise APIError(403, "forbidden", "Admin permission required")
    return user


def expected_version(if_match: str | None = Header(default=None)):
    if if_match is None:
        raise APIError(428, "precondition_required", "If-Match version is required")
    try:
        value = int(if_match.strip('"'))
        if value < 1:
            raise ValueError()
        return value
    except ValueError as exc:
        raise APIError(422, "invalid_version", "If-Match must contain a positive version") from exc
