"""Password and Google identity verification, backed by Firebase user IDs."""

import hashlib
import logging

import bcrypt
import httpx
from firebase_admin import auth
from google.auth import exceptions as google_exceptions
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.firebase import initialize_firebase

logger = logging.getLogger("legal_api")
DUMMY_HASH = bcrypt.hashpw(b"unused-dummy-password", bcrypt.gensalt(rounds=12))


def verify_password(password, encoded_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), encoded_hash.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        return False


def register(repo, body, request_id):
    initialize_firebase()
    password_hash = bcrypt.hashpw(
        body.password.get_secret_value().encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("ascii")
    try:
        identity = auth.create_user(email=body.email, display_name=body.displayName)
    except auth.EmailAlreadyExistsError:
        raise APIError(
            409, "account_exists", "Email already has an account; sign in instead"
        ) from None
    try:

        def create(current):
            if current:
                raise APIError(409, "account_exists", "Account already exists")
            return {
                "email": body.email,
                "displayName": body.displayName,
                "role": "user",
                "isActive": True,
                "passwordHash": password_hash,
                "authSessionVersion": 0,
            }

        return repo.mutate(
            "users",
            identity.uid,
            create,
            actor=identity.uid,
            event="auth.register",
            request_id=request_id,
        )
    except Exception:
        # Delete only when Firestore confirms no profile was created. If outcome is
        # uncertain, keep the identity so a successful write cannot become orphaned.
        try:
            if repo.get("users", identity.uid) is None:
                auth.delete_user(identity.uid)
        except Exception:
            logger.warning("registration cleanup failed; inspect Firebase identity and profile")
        raise


def firebase_legacy_password(email, password):
    settings = get_settings()
    key = settings.firebase_web_api_key or (
        "demo-key" if settings.firebase_auth_emulator_host else ""
    )
    if not key:
        return None
    host = (
        f"http://{settings.firebase_auth_emulator_host}/identitytoolkit.googleapis.com"
        if settings.firebase_auth_emulator_host
        else "https://identitytoolkit.googleapis.com"
    )
    try:
        response = httpx.post(
            f"{host}/v1/accounts:signInWithPassword",
            params={"key": key},
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=5,
            follow_redirects=False,
            trust_env=False,
        )
    except httpx.HTTPError:
        raise APIError(503, "auth_unavailable", "Authentication service is unavailable") from None
    if response.status_code >= 500 or response.status_code == 429:
        raise APIError(503, "auth_unavailable", "Authentication service is unavailable")
    if response.status_code != 200:
        return None
    return response.json().get("localId")


def login(repo, body):
    initialize_firebase()
    password = body.password.get_secret_value()
    try:
        identity = auth.get_user_by_email(body.email)
    except auth.UserNotFoundError:
        bcrypt.checkpw(password.encode("utf-8"), DUMMY_HASH)
        raise APIError(401, "invalid_credentials", "Invalid email or password") from None
    profile = repo.get("users", identity.uid)
    encoded = (profile or {}).get("passwordHash")
    if encoded:
        valid = verify_password(password, encoded)
    else:
        bcrypt.checkpw(password.encode("utf-8"), DUMMY_HASH)
        valid = firebase_legacy_password(body.email, password) == identity.uid
    if not valid:
        raise APIError(401, "invalid_credentials", "Invalid email or password")
    if identity.disabled or (profile and not profile.get("isActive")):
        raise APIError(403, "account_disabled", "Account is disabled")
    if not profile:
        # Existing Firebase users can bootstrap, preserving their original UID.
        from app.services.users import bootstrap

        profile = bootstrap(
            repo,
            {"uid": identity.uid, "email": identity.email, "name": identity.display_name},
            "legacy-login",
        )
    return profile


class TimedGoogleRequest(GoogleRequest):
    def __call__(self, url, method="GET", body=None, headers=None, timeout=5, **kwargs):
        return super().__call__(
            url, method=method, body=body, headers=headers, timeout=timeout, **kwargs
        )


def verify_google(credential):
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise APIError(503, "google_unavailable", "Google Sign-In is not configured")
    try:
        claims = id_token.verify_oauth2_token(
            credential, TimedGoogleRequest(), settings.google_oauth_client_id
        )
    except google_exceptions.TransportError:
        raise APIError(503, "google_unavailable", "Google verification is unavailable") from None
    except ValueError:
        raise APIError(
            401, "invalid_google_token", "Google sign-in could not be verified"
        ) from None
    email, sub = claims.get("email", "").strip().lower(), claims.get("sub", "")
    if not email or not sub or claims.get("email_verified") is not True:
        raise APIError(401, "invalid_google_token", "A verified Google email is required")
    return claims


def google_account(repo, claims, request_id, linking_uid=None):
    initialize_firebase()
    email = claims["email"].strip().lower()
    subject = claims["sub"]
    subject_id = hashlib.sha256(subject.encode()).hexdigest()
    mapping = repo.get("google_identities", subject_id)
    created_identity = False
    if mapping:
        if linking_uid and mapping["userId"] != linking_uid:
            raise APIError(409, "account_exists", "Google account is linked to another user")
        identity = auth.get_user(mapping["userId"])
    else:
        try:
            identity = auth.get_user_by_email(email)
            existing = True
        except auth.UserNotFoundError:
            if linking_uid:
                identity = auth.get_user(linking_uid)
                existing = True
            else:
                try:
                    identity = auth.create_user(
                        email=email,
                        display_name=(claims.get("name") or "User")[:120],
                        email_verified=email.endswith("@gmail.com") or bool(claims.get("hd")),
                    )
                    existing = False
                    created_identity = True
                except auth.EmailAlreadyExistsError:
                    identity = auth.get_user_by_email(email)
                    existing = True
        if linking_uid and identity.uid != linking_uid:
            raise APIError(409, "account_exists", "Google email belongs to another account")
        # A pre-existing Firebase Google provider or our saved subject is proof of
        # linkage. Otherwise require a logged-in session for the same account.
        profile = repo.get("users", identity.uid) if existing else None
        native_link = any(
            getattr(item, "provider_id", None) == "google.com"
            and getattr(item, "uid", None) == subject
            for item in (identity.provider_data or [])
        )
        saved_link = profile and profile.get("googleSubject") == subject
        if existing and linking_uid != identity.uid and not native_link and not saved_link:
            raise APIError(
                409,
                "account_link_required",
                "Sign in with the existing account before linking Google",
            )
    if identity.disabled:
        raise APIError(403, "account_disabled", "Account is disabled")

    def update(current):
        if current:
            if not current.get("isActive"):
                raise APIError(403, "account_disabled", "Account is disabled")
            previous = current.get("googleSubject")
            if previous and previous != subject:
                raise APIError(409, "account_exists", "Account already has another Google identity")
            return {"googleSubject": subject} if not previous else None
        return {
            "email": email,
            "displayName": (claims.get("name") or "User")[:120],
            "role": "user",
            "isActive": True,
            "googleSubject": subject,
            "authSessionVersion": 0,
        }

    try:
        profile = repo.mutate(
            "users",
            identity.uid,
            update,
            actor=identity.uid,
            event="auth.google_linked",
            request_id=request_id,
        )
    except Exception:
        if created_identity:
            try:
                if repo.get("users", identity.uid) is None:
                    auth.delete_user(identity.uid)
            except Exception:
                logger.warning(
                    "Google registration cleanup failed; inspect Firebase identity and profile"
                )
        raise

    def map_identity(current):
        if current and current.get("userId") != identity.uid:
            raise APIError(409, "account_exists", "Google account is linked to another user")
        return None if current else {"userId": identity.uid}

    repo.mutate(
        "google_identities",
        subject_id,
        map_identity,
        actor=identity.uid,
        event="auth.google_identity_created",
        request_id=request_id,
    )
    return profile
