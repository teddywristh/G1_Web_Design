"""Small account and session API; credentials are never returned or logged."""

import hmac
import secrets

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from firebase_admin import auth

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import verify_firebase_token
from app.dependencies import current_user, get_repository
from app.schemas.auth import GoogleSignIn, Login, Register, SessionPage, SessionUser
from app.services import auth_accounts, auth_sessions

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def issue(repo, response, user, request_id):
    token, csrf = auth_sessions.create(repo, user, request_id)
    auth_sessions.set_cookie(response, token)
    return {"user": user, "csrfToken": csrf}


@router.post("/register", response_model=SessionUser, status_code=201)
def register(body: Register, request: Request, response: Response, repo=Depends(get_repository)):
    auth_sessions.require_json(request)
    user = auth_accounts.register(repo, body, request.state.request_id)
    return issue(repo, response, user, request.state.request_id)


@router.post("/login", response_model=SessionUser)
def login(body: Login, request: Request, response: Response, repo=Depends(get_repository)):
    auth_sessions.require_json(request)
    user = auth_accounts.login(repo, body)
    return issue(repo, response, user, request.state.request_id)


@router.get("/google/challenge")
def google_challenge(request: Request, response: Response):
    auth_sessions.check_origin(request)
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise APIError(503, "google_unavailable", "Google Sign-In is not configured")
    nonce = secrets.token_urlsafe(32)
    response.set_cookie(
        "legal_google_nonce",
        nonce,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/api/v1/auth/google",
        max_age=300,
    )
    return {"nonce": nonce}


@router.post("/google", response_model=SessionUser)
def google(body: GoogleSignIn, request: Request, response: Response, repo=Depends(get_repository)):
    auth_sessions.require_json(request)
    linking_uid = None
    if request.cookies.get(auth_sessions.COOKIE):
        try:
            _, profile = auth_sessions.authenticate(repo, request)
            linking_uid = profile["id"]
        except APIError as exc:
            if exc.status not in (401,):
                raise
    claims = auth_accounts.verify_google(body.credential.get_secret_value())
    nonce = request.cookies.get("legal_google_nonce", "")
    claim_nonce = claims.get("nonce")
    if (
        not nonce
        or not nonce.isascii()
        or not isinstance(claim_nonce, str)
        or not claim_nonce.isascii()
        or not hmac.compare_digest(nonce, claim_nonce)
    ):
        raise APIError(401, "invalid_google_token", "Google sign-in could not be verified")
    response.delete_cookie(
        "legal_google_nonce",
        path="/api/v1/auth/google",
        httponly=True,
        secure=get_settings().auth_cookie_secure,
        samesite=get_settings().auth_cookie_samesite,
    )
    user = auth_accounts.google_account(repo, claims, request.state.request_id, linking_uid)
    return issue(repo, response, user, request.state.request_id)


@router.get("/me", response_model=SessionUser)
def me(user=Depends(current_user), claims=Depends(verify_firebase_token)):
    if "_sessionId" not in claims:
        raise APIError(400, "session_required", "Use a browser session for this endpoint")
    return {"user": user, "csrfToken": claims["_csrfToken"]}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, repo=Depends(get_repository)):
    auth_sessions.require_json(request)
    if request.cookies.get(auth_sessions.COOKIE):
        try:
            session, user = auth_sessions.authenticate(repo, request)
            auth_sessions.revoke(repo, user, session["id"], request.state.request_id)
        except APIError as exc:
            if exc.status != 401 and exc.code != "account_disabled":
                raise
    auth_sessions.clear_cookie(response)
    return None


@router.post("/logout-all", status_code=204)
def logout_all(
    request: Request, response: Response, user=Depends(current_user), repo=Depends(get_repository)
):
    auth_sessions.require_json(request)
    # Revoke Firebase refresh tokens as well as all application sessions.
    auth.revoke_refresh_tokens(user["id"])

    def increment(current):
        if not current or not current.get("isActive"):
            raise APIError(403, "account_disabled", "Account is disabled")
        return {"authSessionVersion": current.get("authSessionVersion", 0) + 1}

    repo.mutate(
        "users",
        user["id"],
        increment,
        actor=user["id"],
        event="auth.all_sessions_revoked",
        request_id=request.state.request_id,
    )
    auth_sessions.clear_cookie(response)
    return None


@router.get("/sessions", response_model=SessionPage)
def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=3000),
    user=Depends(current_user),
    claims=Depends(verify_firebase_token),
    repo=Depends(get_repository),
):
    result = repo.page(
        "auth_sessions", filters=[("userId", "==", user["id"])], limit=limit, cursor=cursor
    )
    now = auth_sessions.utcnow()
    return {
        "items": [
            {
                "id": row["id"],
                "createdAt": row["createdAt"],
                "expiresAt": row["expiresAt"],
                "current": row["id"] == claims.get("_sessionId"),
                "active": not row.get("revokedAt")
                and row["expiresAt"] > now
                and row.get("sessionVersion", 0) == user.get("authSessionVersion", 0),
            }
            for row in result["items"]
        ],
        "nextCursor": result["nextCursor"],
    }


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    request: Request,
    response: Response,
    session_id: str = Path(pattern=r"^[0-9a-f]{64}$"),
    user=Depends(current_user),
    claims=Depends(verify_firebase_token),
    repo=Depends(get_repository),
):
    auth_sessions.revoke(repo, user, session_id, request.state.request_id)
    if session_id == claims.get("_sessionId"):
        auth_sessions.clear_cookie(response)
    return None
