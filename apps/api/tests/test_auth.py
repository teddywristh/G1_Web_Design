from types import SimpleNamespace
from uuid import uuid4

import bcrypt
import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth

from app.core.config import get_settings
from app.dependencies import get_repository
from app.main import create_app
from app.services import auth_accounts, auth_sessions
from tests.test_backend import MemoryRepository


@pytest.fixture
def setup(monkeypatch):
    repo = MemoryRepository()
    identities = {}

    def get_by_email(email):
        for item in identities.values():
            if item.email == email:
                return item
        raise auth.UserNotFoundError("missing")

    def create_user(email, display_name, **kwargs):
        if any(item.email == email for item in identities.values()):
            raise auth.EmailAlreadyExistsError("exists", None, None)
        item = SimpleNamespace(
            uid=uuid4().hex,
            email=email,
            display_name=display_name,
            disabled=False,
            provider_data=[],
        )
        identities[item.uid] = item
        return item

    monkeypatch.setattr(auth_accounts, "initialize_firebase", lambda: {})
    monkeypatch.setattr(auth, "get_user_by_email", get_by_email)
    monkeypatch.setattr(auth, "get_user", lambda uid: identities[uid])
    monkeypatch.setattr(auth, "create_user", create_user)
    monkeypatch.setattr(auth, "delete_user", lambda uid: identities.pop(uid))
    monkeypatch.setattr(auth, "revoke_refresh_tokens", lambda uid: None)
    monkeypatch.setattr(auth, "update_user", lambda uid, **kwargs: identities[uid])
    monkeypatch.setattr(get_settings(), "google_oauth_client_id", "test-client")
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, repo, identities


def signup(client, email="test@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "displayName": "Test"},
    )


def test_email_ignores_case_and_names_keep_case(setup):
    client, repo, identities = setup
    assert signup(client, "Mixed@Example.com").status_code == 201
    assert signup(client, "mixed@example.COM").status_code == 409
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "MIXED@example.com", "password": "password123"}
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password123", "displayName": "test"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["displayName"] == "test"
    assert len(identities) == 2


def test_password_otp_reset_and_replay(setup, monkeypatch):
    from app.services import password_reset

    client, repo, identities = setup
    assert signup(client).status_code == 201
    old_session = client.cookies.get("legal_session")
    monkeypatch.setattr(password_reset, "initialize_firebase", lambda: {})
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.test")
    monkeypatch.setattr(get_settings(), "smtp_username", "mail@test.com")
    from pydantic import SecretStr

    monkeypatch.setattr(get_settings(), "smtp_password", SecretStr("test"))
    sent = []
    monkeypatch.setattr(password_reset, "send_email", lambda email, otp: sent.append((email, otp)))
    response = client.post("/api/v1/auth/password/otp", json={"email": "TEST@example.com"})
    assert response.status_code == 200
    assert len(sent) == 1 and sent[0][0] == "test@example.com"
    assert sent[0][1] not in response.text
    assert (
        client.post("/api/v1/auth/password/otp", json={"email": "test@example.com"}).status_code
        == 429
    )
    payload = {"email": "test@example.com", "password": "newpassword123", "otp": sent[0][1]}
    wrong = "000000" if payload["otp"] != "000000" else "111111"
    assert (
        client.post("/api/v1/auth/password/reset", json={**payload, "otp": wrong}).status_code
        == 400
    )
    assert client.post("/api/v1/auth/password/reset", json=payload).status_code == 204
    assert client.post("/api/v1/auth/password/reset", json=payload).status_code == 400
    client.cookies.set("legal_session", old_session)
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": payload["email"], "password": "password123"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
        ).status_code
        == 200
    )
    assert (
        client.post("/api/v1/auth/password/otp", json={"email": "missing@example.com"}).status_code
        == 200
    )
    assert len(sent) == 1


def test_password_reset_requires_email_configuration(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setattr(get_settings(), "smtp_host", "")
    assert (
        client.post("/api/v1/auth/password/otp", json={"email": "test@example.com"}).status_code
        == 503
    )


@pytest.mark.parametrize("expired,attempts", [(True, 0), (False, 5)])
def test_reset_rejects_expired_or_exhausted_code(setup, monkeypatch, expired, attempts):
    import hashlib
    from datetime import timedelta

    from app.core.errors import APIError
    from app.repositories.backend import utcnow
    from app.schemas.auth import PasswordReset
    from app.services import password_reset

    _, repo, _ = setup
    monkeypatch.setattr(password_reset, "initialize_firebase", lambda: {})
    email = "test@example.com"
    repo.rows[("password_resets", hashlib.sha256(email.encode()).hexdigest())] = {
        "consumed": False,
        "expiresAt": utcnow() + timedelta(minutes=-1 if expired else 10),
        "attempts": attempts,
    }
    with pytest.raises(APIError) as error:
        password_reset.reset_password(
            repo, PasswordReset(email=email, password="newpassword123", otp="123456"), "test"
        )
    assert error.value.code == "invalid_otp"


def test_registration_login_and_csrf(setup):
    client, repo, identities = setup
    response = signup(client)
    assert response.status_code == 201, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    user = response.json()["user"]
    uid = user["id"]
    assert "passwordHash" not in response.text
    assert bcrypt.checkpw(b"password123", repo.get("users", uid)["passwordHash"].encode())
    token = client.cookies.get("legal_session")
    assert repo.get("auth_sessions", auth_sessions.digest(token))["userId"] == uid
    csrf = response.json()["csrfToken"]
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout", json={}).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/logout",
            json={},
            headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/auth/logout", json={}, headers={"X-CSRF-Token": csrf}).status_code
        == 204
    )
    client.cookies.set("legal_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "test@example.com", "password": "incorrect"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "test@example.com", "password": "password123"}
        ).status_code
        == 200
    )
    assert signup(client).status_code == 409
    invalid = signup(client, email="not-an-email")
    assert invalid.status_code == 422 and "password123" not in invalid.text
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "short", "displayName": "Test"},
        ).status_code
        == 422
    )


def test_all_sessions_revoked_and_account_disabled(setup):
    client, repo, identities = setup
    first = signup(client)
    uid = first.json()["user"]["id"]
    old_cookie = client.cookies.get("legal_session")
    login = client.post(
        "/api/v1/auth/login", json={"email": "test@example.com", "password": "password123"}
    )
    assert (
        client.post(
            "/api/v1/auth/logout-all", json={}, headers={"X-CSRF-Token": login.json()["csrfToken"]}
        ).status_code
        == 204
    )
    client.cookies.set("legal_session", old_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    login = client.post(
        "/api/v1/auth/login", json={"email": "test@example.com", "password": "password123"}
    )
    repo.rows[("users", uid)]["isActive"] = False
    assert client.get("/api/v1/auth/me").status_code == 403
    assert client.post("/api/v1/auth/logout", json={}).status_code == 204


def test_legacy_firebase_password_and_google_link(setup, monkeypatch):
    client, repo, identities = setup
    identity = auth.create_user(email="old@example.com", display_name="Old")
    monkeypatch.setattr(
        auth_accounts,
        "firebase_legacy_password",
        lambda email, password: identity.uid if password == "123456" else None,
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": identity.email, "password": "123456"}
    )
    assert response.status_code == 200, response.text
    csrf = response.json()["csrfToken"]
    challenge_response = client.get("/api/v1/auth/google/challenge").json()
    assert challenge_response["clientId"] == "test-client"
    challenge = challenge_response["nonce"]
    claims = {
        "email": "different@gmail.com",
        "sub": "google-sub",
        "nonce": challenge,
        "email_verified": True,
    }
    monkeypatch.setattr(auth_accounts, "verify_google", lambda _: claims)
    linked = client.post(
        "/api/v1/auth/google",
        json={"credential": "google-test-credential-12345"},
        headers={"X-CSRF-Token": csrf},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["user"]["id"] == identity.uid
    assert len(identities) == 1
    client.cookies.clear()
    challenge = client.get("/api/v1/auth/google/challenge").json()["nonce"]
    claims["nonce"] = "incorrect"
    assert (
        client.post(
            "/api/v1/auth/google", json={"credential": "google-test-credential-12345"}
        ).status_code
        == 401
    )
    claims["nonce"] = challenge
    assert (
        client.post(
            "/api/v1/auth/google", json={"credential": "google-test-credential-12345"}
        ).status_code
        == 200
    )
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/google", json={"credential": "google-test-credential-12345"}
        ).status_code
        == 401
    )


def test_google_cannot_take_over_existing_email(setup, monkeypatch):
    client, repo, identities = setup
    signup(client)
    client.cookies.clear()
    nonce = client.get("/api/v1/auth/google/challenge").json()["nonce"]
    monkeypatch.setattr(
        auth_accounts,
        "verify_google",
        lambda _: {"email": "test@example.com", "sub": "attacker", "nonce": nonce},
    )
    response = client.post(
        "/api/v1/auth/google", json={"credential": "google-test-credential-12345"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_link_required"
