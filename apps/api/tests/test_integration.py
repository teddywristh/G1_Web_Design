"""Credential-free end-to-end tests. Run only against demo-legal-api emulators."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.firebase import initialize_firebase
from app.main import create_app
from app.repositories.backend import BackendRepository, utcnow
from app.services import documents

pytestmark = pytest.mark.integration
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"


@pytest.fixture
def environment():
    clients = initialize_firebase()
    assert clients["db"].project == "demo-legal-api"
    repo = BackendRepository(clients["db"])
    with TestClient(create_app(), raise_server_exceptions=False) as api:
        yield api, repo, clients["storage"]


def signup(api):
    email = f"{uuid4().hex}@example.com"
    result = httpx.post(
        "http://"
        + os.environ["FIREBASE_AUTH_EMULATOR_HOST"]
        + "/identitytoolkit.googleapis.com/v1/accounts:signUp?key=demo-key",
        json={"email": email, "password": "TestPassword123!", "returnSecureToken": True},
        timeout=10,
    )
    assert result.status_code == 200, result.text
    identity = result.json()
    headers = {"Authorization": "Bearer " + identity["idToken"]}
    boot = api.post("/api/v1/users/me/bootstrap", headers=headers)
    assert boot.status_code == 200, boot.text
    return identity["localId"], headers


def admin_session(api, repo):
    uid, headers = signup(api)
    repo.mutate(
        "users",
        uid,
        lambda _: {"role": "admin"},
        actor="test",
        event="user.admin_granted",
        request_id="integration",
    )
    return uid, headers


def create(api, headers):
    response = api.post(
        "/api/v1/admin/documents",
        headers=headers,
        json={
            "title": "Luật Đất Đai " + uuid4().hex,
            "documentNumber": "01/" + uuid4().hex,
            "documentType": "law",
            "issuingAuthority": "Assembly",
            "issueDate": "2026-01-01",
            "effectiveDate": "2026-02-01",
            "status": "effective",
            "sourceUrl": "https://example.com/law",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload(api, headers, doc):
    response = api.put(
        f"/api/v1/admin/documents/{doc['id']}/file",
        content=PDF,
        headers={**headers, "If-Match": str(doc["version"]), "Content-Type": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_complete_flow_and_blocked_account(environment):
    api, repo, bucket = environment
    _, admin = admin_session(api, repo)
    uid, reader = signup(api)
    assert api.get("/ready").status_code == 200
    assert api.get("/api/v1/admin/users", headers=reader).status_code == 403
    invalid = api.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid"})
    assert invalid.status_code == 401
    doc = create(api, admin)
    doc_id = doc["id"]
    assert api.get(f"/api/v1/documents/{doc_id}", headers=reader).status_code == 404
    available = upload(api, admin, doc)
    assert "storagePath" not in available
    assert api.get(f"/api/v1/documents/{doc_id}", headers=reader).status_code == 200
    file_response = api.get(f"/api/v1/documents/{doc_id}/download", headers=reader)
    assert file_response.status_code == 200, file_response.text
    assert file_response.content == PDF
    assert file_response.headers["cache-control"] == "no-store"
    for query in (
        {},
        {"documentNumber": doc["documentNumber"]},
        {"titlePrefix": "luat dat"},
        {"status": "effective"},
        {"documentType": "law"},
        {"issuingAuthority": "Assembly"},
        {"issueDateFrom": "2026-01-01", "issueDateTo": "2026-12-31"},
    ):
        response = api.get("/api/v1/documents", params=query, headers=reader)
        assert response.status_code == 200, response.text
    patched = api.patch(
        f"/api/v1/admin/documents/{doc_id}",
        headers={**admin, "If-Match": str(available["version"])},
        json={"title": "Luật đổi tên"},
    )
    assert patched.status_code == 200, patched.text
    assert (
        api.patch(
            f"/api/v1/admin/documents/{doc_id}",
            headers={**admin, "If-Match": "1"},
            json={"title": "Lost write"},
        ).status_code
        == 409
    )
    version = repo.get("users", uid)["version"]
    blocked = api.patch(
        f"/api/v1/admin/users/{uid}",
        headers={**admin, "If-Match": str(version)},
        json={"isActive": False},
    )
    assert blocked.status_code == 200, blocked.text
    assert api.get("/api/v1/users/me", headers=reader).status_code == 403
    assert api.post("/api/v1/users/me/bootstrap", headers=reader).status_code == 403
    assert api.get(f"/api/v1/documents/{doc_id}/download", headers=reader).status_code == 403
    deleted = api.delete(
        f"/api/v1/admin/documents/{doc_id}",
        headers={**admin, "If-Match": str(patched.json()["version"])},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["fileState"] == "deleted"
    assert api.get(f"/api/v1/documents/{doc_id}", headers=admin).status_code == 404
    logs = api.get(
        "/api/v1/admin/audit-logs",
        headers=admin,
        params={"event": "document.delete_complete", "limit": 100},
    )
    assert logs.status_code == 200, logs.text
    assert any(log["targetId"] == doc_id for log in logs.json()["items"])
    assert (
        api.get("/api/v1/admin/users", params={"isActive": False}, headers=admin).status_code == 200
    )


def test_cursor_tied_sort_values_and_scope(environment):
    api, repo, bucket = environment
    _, admin = admin_session(api, repo)
    created = [create(api, admin) for _ in range(3)]
    now = utcnow()
    for doc in created:
        upload(api, admin, doc)
        repo.db.collection("legal_documents").document(doc["id"]).update(
            {
                "createdAt": now,
                "documentType": "tie-" + created[0]["id"],
            }
        )
    params = {"documentType": "tie-" + created[0]["id"], "limit": 1}
    seen = []
    while True:
        response = api.get("/api/v1/documents", params=params, headers=admin)
        assert response.status_code == 200, response.text
        payload = response.json()
        seen.extend(item["id"] for item in payload["items"])
        if not payload["nextCursor"]:
            break
        params["cursor"] = payload["nextCursor"]
        assert len(seen) <= 3
    assert len(seen) == len(set(seen)) == 3
    assert set(seen) == {doc["id"] for doc in created}
    response = api.get(
        "/api/v1/documents", params={**params, "documentType": "other"}, headers=admin
    )
    assert response.status_code == 422
    for doc in created:
        current = repo.get("legal_documents", doc["id"])
        documents.delete_document(repo, bucket, doc["id"], "test", "cleanup", current["version"])


def test_real_transaction_prevents_lost_updates(environment):
    api, repo, bucket = environment
    uid, admin = admin_session(api, repo)
    doc = create(api, admin)

    def update(title):
        try:
            documents.patch_document(repo, doc["id"], {"title": title}, uid, "race", doc["version"])
            return "ok"
        except Exception as exc:
            return getattr(exc, "code", type(exc).__name__)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(update, ["First writer", "Second writer"]))
    assert sorted(results) == ["ok", "version_conflict"]
    current = repo.get("legal_documents", doc["id"])
    documents.delete_document(repo, bucket, doc["id"], uid, "cleanup", current["version"])


def test_actual_file_reconciliation_and_missing_object_delete(environment):
    api, repo, bucket = environment
    uid, admin = admin_session(api, repo)
    doc = create(api, admin)
    path = f"legal-documents/{doc['id']}/{uuid4().hex}.pdf"
    bucket.blob(path).upload_from_string(PDF, content_type="application/pdf")
    repo.db.collection("legal_documents").document(doc["id"]).update(
        {
            "uploadLease": {
                "id": "expired",
                "path": path,
                "expiresAt": utcnow() - timedelta(seconds=1),
            },
        }
    )
    result = documents.reconcile(repo, bucket, dry_run=False)
    assert result["expiredUploads"] >= 1
    assert not bucket.blob(path).exists()
    state = repo.get("legal_documents", doc["id"])
    assert state["fileState"] == "upload_failed"
    uploaded = upload(api, admin, state)
    object_path = repo.get("legal_documents", doc["id"])["storagePath"]
    bucket.blob(object_path).delete()
    response = api.delete(
        f"/api/v1/admin/documents/{doc['id']}",
        headers={**admin, "If-Match": str(uploaded["version"])},
    )
    assert response.status_code == 200, response.text
    assert response.json()["fileState"] == "deleted"


def test_client_rules_deny_direct_data_access(environment):
    api, repo, _ = environment
    uid, headers = signup(api)
    project = "demo-legal-api"
    firestore_url = (
        "http://"
        + os.environ["FIRESTORE_EMULATOR_HOST"]
        + f"/v1/projects/{project}/databases/(default)/documents"
    )
    storage_url = os.environ["STORAGE_EMULATOR_HOST"] + f"/v0/b/{project}.appspot.com/o"
    for auth_headers in ({}, headers):
        assert (
            httpx.get(firestore_url + "/users/" + uid, headers=auth_headers, timeout=10).status_code
            == 403
        )
        assert (
            httpx.patch(
                firestore_url + "/users/" + uid,
                headers=auth_headers,
                json={"fields": {"role": {"stringValue": "admin"}}},
                timeout=10,
            ).status_code
            == 403
        )
        assert httpx.get(storage_url, headers=auth_headers, timeout=10).status_code in {401, 403}
        assert httpx.post(
            storage_url,
            params={"name": "legal-documents/forbidden.pdf", "uploadType": "media"},
            content=PDF,
            headers={**auth_headers, "Content-Type": "application/pdf"},
            timeout=10,
        ).status_code in {401, 403}


def test_firebase_disabled_and_expired_tokens_are_rejected(environment):
    import base64
    import json
    import time

    from firebase_admin import auth

    api, repo, _ = environment
    uid, headers = signup(api)
    auth.update_user(uid, disabled=True)
    assert api.get("/api/v1/users/me", headers=headers).status_code == 401
    auth.update_user(uid, disabled=False)
    token = headers["Authorization"][7:]
    head, payload, signature = token.split(".")
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    data.update(exp=int(time.time()) - 3600, iat=int(time.time()) - 7200)
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    expired = ".".join([head, payload, signature])
    assert (
        api.get("/api/v1/users/me", headers={"Authorization": "Bearer " + expired}).status_code
        == 401
    )


def test_encrypted_ai_credentials_with_real_firebase_authorization(environment, monkeypatch):
    from cryptography.fernet import Fernet
    from pydantic import SecretStr

    from app.core.config import get_settings
    from app.services.ai_connections import connection_id, resolve

    api, repo, _ = environment
    monkeypatch.setattr(
        get_settings(), "ai_credential_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    admin_uid, admin = admin_session(api, repo)
    uid, reader = signup(api)
    secret = "sk-test-emulator-not-a-real-key"
    response = api.put(
        "/api/v1/ai/connections/openai",
        headers=reader,
        json={"apiKey": secret, "expectedVersion": 0},
    )
    assert response.status_code == 200, response.text
    assert secret not in response.text
    stored = repo.get("ai_connections", connection_id("user:" + uid, "openai"))
    assert secret not in str(stored)
    assert resolve(repo, {"id": uid}, "openai", "personal", get_settings()).api_key == secret
    assert (
        api.put(
            "/api/v1/admin/ai/connections/anthropic",
            headers=reader,
            json={"apiKey": secret, "expectedVersion": 0},
        ).status_code
        == 403
    )
    shared = api.put(
        "/api/v1/admin/ai/connections/anthropic",
        headers=admin,
        json={"apiKey": secret, "expectedVersion": 0},
    )
    assert shared.status_code == 200, shared.text
    _, other = signup(api)
    options = api.get("/api/v1/ai/connections", headers=other)
    assert options.status_code == 200, options.text
    assert secret not in options.text
    assert not next(
        x
        for x in options.json()["connections"]
        if x["scope"] == "personal" and x["provider"] == "openai"
    )["configured"]
    assert (
        api.delete(
            "/api/v1/ai/connections/openai",
            headers={**reader, "If-Match": str(response.json()["version"])},
        ).status_code
        == 200
    )
    assert (
        api.delete(
            "/api/v1/admin/ai/connections/anthropic",
            headers={**admin, "If-Match": str(shared.json()["version"])},
        ).status_code
        == 200
    )


def test_password_account_sessions_with_firebase(environment):
    api, repo, _ = environment
    email = f"auth-{uuid4().hex}@example.com"
    response = api.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPassword123!", "displayName": "Auth test"},
    )
    assert response.status_code == 201, response.text
    uid = response.json()["user"]["id"]
    csrf = response.json()["csrfToken"]
    assert repo.get("users", uid)["passwordHash"].startswith("$2")
    assert api.get("/api/v1/auth/me").json()["user"]["id"] == uid
    sessions = api.get("/api/v1/auth/sessions")
    assert sessions.status_code == 200, sessions.text
    assert len(sessions.json()["items"]) == 1 and sessions.json()["items"][0]["current"]
    assert api.post("/api/v1/auth/logout", json={}).status_code == 403
    assert (
        api.post("/api/v1/auth/logout", json={}, headers={"X-CSRF-Token": csrf}).status_code == 204
    )
    assert api.get("/api/v1/auth/me").status_code == 401
    login = api.post("/api/v1/auth/login", json={"email": email, "password": "TestPassword123!"})
    assert login.status_code == 200, login.text
    assert (
        api.post(
            "/api/v1/auth/logout-all", json={}, headers={"X-CSRF-Token": login.json()["csrfToken"]}
        ).status_code
        == 204
    )
    assert api.get("/api/v1/auth/me").status_code == 401
