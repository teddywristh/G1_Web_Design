"""Opaque, server-revocable sessions. Only a digest is stored in Firestore."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from app.core.config import get_settings
from app.core.errors import APIError
from app.repositories.backend import utcnow

COOKIE = "legal_session"


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def check_origin(request):
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().backend_cors_origins:
        raise APIError(403, "invalid_origin", "Origin is not allowed")


def require_json(request):
    check_origin(request)
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise APIError(415, "unsupported_media_type", "Content-Type must be application/json")


def create(repo, user, request_id):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    session_id = digest(token)
    expires = utcnow() + timedelta(hours=get_settings().auth_session_hours)
    fields = {
        "userId": user["id"],
        "sessionVersion": user.get("authSessionVersion", 0),
        "csrfToken": csrf,
        "expiresAt": expires,
        "revokedAt": None,
    }
    repo.mutate(
        "auth_sessions",
        session_id,
        lambda current: fields if current is None else None,
        actor=user["id"],
        event="auth.session_created",
        request_id=request_id,
    )
    return token, csrf


def set_cookie(response, token):
    settings = get_settings()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
        max_age=settings.auth_session_hours * 3600,
    )
    response.headers["Cache-Control"] = "no-store"


def clear_cookie(response):
    settings = get_settings()
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


def authenticate(repo, request, *, unsafe=None):
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 100:
        raise APIError(401, "unauthenticated", "Sign in required")
    session = repo.get("auth_sessions", digest(token))
    if (
        not session
        or session.get("revokedAt")
        or session.get("expiresAt") is None
        or session["expiresAt"] <= utcnow()
    ):
        raise APIError(401, "unauthenticated", "Session expired or revoked")
    profile = repo.get("users", session["userId"])
    if not profile or not profile.get("isActive"):
        raise APIError(403, "account_disabled", "Account is disabled")
    if session.get("sessionVersion", 0) != profile.get("authSessionVersion", 0):
        raise APIError(401, "unauthenticated", "Session expired or revoked")
    if unsafe is None:
        unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
    if unsafe:
        check_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if (
            not csrf
            or not csrf.isascii()
            or not hmac.compare_digest(csrf, session.get("csrfToken", ""))
        ):
            raise APIError(403, "csrf_failed", "Invalid CSRF token")
    return session, profile


def revoke(repo, user, session_id, request_id):
    def change(current):
        if not current or current.get("userId") != user["id"]:
            raise APIError(404, "not_found", "Session not found")
        if current.get("revokedAt"):
            return None
        return {"revokedAt": utcnow()}

    repo.mutate(
        "auth_sessions",
        session_id,
        change,
        actor=user["id"],
        event="auth.session_revoked",
        request_id=request_id,
    )
