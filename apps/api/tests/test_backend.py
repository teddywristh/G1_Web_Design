from copy import deepcopy
from datetime import timedelta
from threading import RLock
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import ServiceUnavailable

from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.core.security import verify_firebase_token
from app.dependencies import get_bucket, get_repository
from app.main import create_app
from app.repositories.backend import decode_cursor, encode_cursor, utcnow
from app.schemas import DocumentPatch, DocumentQuery
from app.services import documents, users


class MemoryRepository:
    """Transactional domain fake; real query and transaction coverage is in integration tests."""

    def __init__(self):
        self.rows = {}
        self.audit = []
        self.lock = RLock()
        self.fail_event = None

    def scan(self, collection):
        return iter(
            [deepcopy(value) for (name, _), value in self.rows.items() if name == collection]
        )

    def get(self, collection, doc_id):
        return deepcopy(self.rows.get((collection, doc_id)))

    def mutate(self, collection, doc_id, change, *, actor, event, request_id):
        with self.lock:
            if event == self.fail_event:
                raise ServiceUnavailable("simulated outage")
            current = self.get(collection, doc_id)
            patch = change(current)
            if patch is not None:
                data = {
                    **(current or {"id": doc_id, "createdAt": utcnow()}),
                    **patch,
                    "updatedAt": utcnow(),
                    "version": (current or {}).get("version", 0) + 1,
                }
                self.rows[(collection, doc_id)] = data
                self.audit.append({"event": event, "actorId": actor})
            return self.get(collection, doc_id)


@pytest.fixture
def repo():
    return MemoryRepository()


@pytest.fixture
def api(repo):
    app = create_app()
    bucket = Mock()
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_bucket] = lambda: bucket
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, app, bucket


def identity(app, uid="reader"):
    app.dependency_overrides[verify_firebase_token] = lambda: {
        "uid": uid,
        "email": f"{uid}@example.com",
        "name": "Example",
        "role": "admin",
    }


def profile(repo, uid="reader", role="user"):
    data = users.bootstrap(repo, {"uid": uid}, "test")
    repo.rows[("users", uid)]["role"] = role
    return data


@pytest.fixture
def document(repo):
    return documents.create_document(
        repo,
        {
            "title": "Luật Đất Đai",
            "documentNumber": "01/2026/QH",
            "documentType": "law",
            "issuingAuthority": "Assembly",
            "issueDate": "2026-01-01",
            "effectiveDate": None,
            "status": "effective",
            "sourceUrl": None,
        },
        "admin",
        "test",
    )


def test_auth_errors_health_and_request_id(api):
    client, app, _ = api
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/api/v1/users/me", headers={"X-Request-ID": "trace_123"})
    assert response.status_code == 401
    assert response.json()["requestId"] == "trace_123"
    assert response.headers["www-authenticate"] == "Bearer"


def test_bootstrap_idempotent_never_trusts_token_role(api, repo):
    client, app, _ = api
    identity(app)
    first = client.post("/api/v1/users/me/bootstrap")
    assert first.status_code == 200
    assert first.json()["role"] == "user"
    assert client.post("/api/v1/users/me/bootstrap").json()["version"] == first.json()["version"]
    assert client.get("/api/v1/admin/users").status_code == 403
    repo.rows[("users", "reader")]["isActive"] = False
    assert client.get("/api/v1/users/me").status_code == 403
    assert client.post("/api/v1/users/me/bootstrap").status_code == 403


def test_profile_allowlist_versions_and_response_redaction(api, repo):
    client, app, _ = api
    identity(app)
    profile(repo)
    repo.rows[("users", "reader")]["privateField"] = "secret"
    assert "privateField" not in client.get("/api/v1/users/me").json()
    assert client.patch("/api/v1/users/me", json={"displayName": "New"}).status_code == 428
    assert (
        client.patch(
            "/api/v1/users/me",
            headers={"If-Match": "1"},
            json={"role": "admin", "displayName": "New"},
        ).status_code
        == 422
    )
    updated = client.patch(
        "/api/v1/users/me", headers={"If-Match": '"1"'}, json={"displayName": "New"}
    )
    assert updated.status_code == 200
    assert updated.headers["etag"] == '"2"'
    assert (
        client.patch(
            "/api/v1/users/me", headers={"If-Match": "1"}, json={"displayName": "Lost write"}
        ).status_code
        == 409
    )


def test_admin_cannot_lock_self(api, repo):
    client, app, _ = api
    identity(app, "admin")
    profile(repo, "admin", "admin")
    response = client.patch(
        "/api/v1/admin/users/admin", headers={"If-Match": "1"}, json={"isActive": False}
    )
    assert response.status_code == 409


def test_hidden_document_and_upload_validation(api, repo, document):
    client, app, bucket = api
    identity(app)
    profile(repo)
    assert client.get(f"/api/v1/documents/{document['id']}").status_code == 404
    identity(app, "admin")
    profile(repo, "admin", "admin")
    endpoint = f"/api/v1/admin/documents/{document['id']}/file"
    headers = {"If-Match": "1", "Content-Type": "application/pdf"}
    assert client.put(endpoint, content=b"not-pdf", headers=headers).status_code == 415
    assert (
        client.put(
            endpoint, content=b"%PDF-1.4", headers={**headers, "Content-Type": "text/plain"}
        ).status_code
        == 415
    )
    maximum = get_settings().max_upload_size_bytes
    assert (
        client.put(
            endpoint, content=b"%PDF-", headers={**headers, "Content-Length": str(maximum + 1)}
        ).status_code
        == 413
    )
    response = client.put(endpoint, content=b"%PDF-1.4\n%%EOF", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["fileState"] == "available"
    assert "storagePath" not in response.json()
    calls = bucket.blob.return_value.upload_from_filename.call_count
    retry = client.put(endpoint, content=b"%PDF-1.4\n%%EOF", headers=headers)
    assert retry.status_code == 200
    assert bucket.blob.return_value.upload_from_filename.call_count == calls
    assert client.put(endpoint, content=b"%PDF-changed", headers=headers).status_code == 409


def test_streaming_size_limit_without_length(api, repo, document):
    client, app, _ = api
    identity(app, "admin")
    profile(repo, "admin", "admin")
    settings = get_settings()
    original = settings.max_upload_size_bytes
    try:
        settings.max_upload_size_bytes = 10
        response = client.put(
            f"/api/v1/admin/documents/{document['id']}/file",
            content=iter([b"%PDF-", b"123456"]),
            headers={"Content-Type": "application/pdf", "If-Match": "1"},
        )
        assert response.status_code == 413
    finally:
        settings.max_upload_size_bytes = original


def test_upload_failure_retains_lease_for_recovery(repo, document, tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-")
    bucket = Mock()
    bucket.blob.return_value.upload_from_filename.side_effect = ServiceUnavailable("outage")
    with pytest.raises(APIError) as error:
        documents.upload_document(
            repo, bucket, document["id"], str(source), 5, "hash", "admin", "test", 1
        )
    assert error.value.status == 503
    state = repo.get("legal_documents", document["id"])
    assert state["fileState"] == "upload_failed"
    assert state["uploadLease"]["path"].endswith(".pdf")
    assert state["storagePath"] is None


def test_firestore_failure_after_object_upload_is_recoverable(repo, document, tmp_path):
    bucket = Mock()
    bucket.list_blobs.return_value = []
    repo.fail_event = "document.upload_complete"
    with pytest.raises(ServiceUnavailable):
        documents.upload_document(
            repo, bucket, document["id"], "source.pdf", 5, "hash", "admin", "test", 1
        )
    state = repo.rows[("legal_documents", document["id"])]
    assert state["uploadLease"]
    state["uploadLease"]["expiresAt"] = utcnow() - timedelta(seconds=1)
    repo.fail_event = None
    assert documents.reconcile(repo, bucket)["expiredUploads"] == 1
    assert repo.get("legal_documents", document["id"])["uploadLease"]
    result = documents.reconcile(repo, bucket, dry_run=False)
    assert result["errors"] == 0
    assert repo.get("legal_documents", document["id"])["fileState"] == "upload_failed"
    assert repo.get("legal_documents", document["id"])["uploadLease"] is None


def test_upload_concurrency_and_delete_during_upload(repo, document):
    current = repo.rows[("legal_documents", document["id"])]
    current["uploadLease"] = {
        "id": "other",
        "path": "other.pdf",
        "expiresAt": utcnow() + timedelta(minutes=5),
    }
    with pytest.raises(APIError) as error:
        documents.upload_document(
            repo, Mock(), document["id"], "unused", 5, "hash", "admin", "test", 1
        )
    assert error.value.code == "upload_in_progress"
    with pytest.raises(APIError) as error:
        documents.delete_document(repo, Mock(), document["id"], "admin", "test", 1)
    assert error.value.code == "upload_in_progress"


def test_failed_delete_hides_document_and_can_retry(repo, document):
    state = repo.rows[("legal_documents", document["id"])]
    state.update(fileState="available", storagePath="legal-documents/x/a.pdf")
    bucket = Mock()
    bucket.blob.return_value.delete.side_effect = ServiceUnavailable("outage")
    with pytest.raises(ServiceUnavailable):
        documents.delete_document(repo, bucket, document["id"], "admin", "test", 1)
    hidden = repo.get("legal_documents", document["id"])
    assert hidden["fileState"] == "deletion_pending"
    with pytest.raises(APIError):
        documents.ensure_document(hidden, public=True)
    bucket.blob.return_value.delete.side_effect = None
    deleted = documents.delete_document(
        repo, bucket, document["id"], "admin", "test", hidden["version"]
    )
    assert deleted["fileState"] == "deleted"
    assert (
        documents.delete_document(repo, bucket, document["id"], "admin", "test", 1)["fileState"]
        == "deleted"
    )


def test_schema_and_query_contract():
    with pytest.raises(ValueError):
        DocumentPatch(title=None)
    with pytest.raises(ValueError):
        DocumentPatch(storagePath="arbitrary")
    assert DocumentPatch(effectiveDate=None).model_fields_set == {"effectiveDate"}
    with pytest.raises(ValueError):
        DocumentQuery(status="effective", titlePrefix="law")
    with pytest.raises(ValueError):
        DocumentQuery(issueDateFrom="2026-02-01", issueDateTo="2026-01-01")
    assert documents.normalize("  LUẬT Đất Đai  ") == "luat dat dai"


def test_cursor_roundtrip_and_scope():
    now = utcnow()
    cursor = encode_cursor("scope", now, "doc")
    assert decode_cursor(cursor, "scope") == (now, "doc")
    for bad in [cursor, "bad!", encode_cursor("wrong", "x", "../doc")]:
        with pytest.raises(APIError):
            decode_cursor(bad, "different")


def test_production_config_rejects_emulators_and_demo():
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="production")
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            app_env="production",
            firebase_auth_emulator_host=None,
            firestore_emulator_host=None,
            storage_emulator_host=None,
            backend_cors_origins=["*"],
            firebase_project_id="real-project",
            firebase_storage_bucket="real-project.appspot.com",
        )


def test_ready_failure_is_503(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr("app.main.initialize_firebase", Mock(side_effect=RuntimeError("secret")))
    result = client.get("/ready")
    assert result.status_code == 503
    assert "secret" not in result.text


def test_reconcile_retains_referenced_and_recent_files_but_removes_old_orphan(repo, document):
    bucket = Mock()
    active = Mock(name="active")
    active.name = f"legal-documents/{document['id']}/active.pdf"
    active.time_created = utcnow() - timedelta(hours=2)
    active.generation = 11
    repo.rows[("legal_documents", document["id"])]["storagePath"] = active.name
    recent = Mock(name="recent")
    recent.name = "legal-documents/missing/recent.pdf"
    recent.time_created = utcnow()
    orphan = Mock(name="orphan")
    orphan.name = "legal-documents/missing/old.pdf"
    orphan.time_created = utcnow() - timedelta(hours=2)
    orphan.generation = 13
    bucket.list_blobs.return_value = [active, recent, orphan]
    dry = documents.reconcile(repo, bucket)
    assert dry["orphanFiles"] == 1
    orphan.delete.assert_not_called()
    result = documents.reconcile(repo, bucket, dry_run=False)
    assert result["errors"] == 0
    orphan.delete.assert_called_once_with(if_generation_match=13, timeout=10, retry=None)
    active.delete.assert_not_called()
    recent.delete.assert_not_called()


def test_auth_verifier_rejects_revoked_and_expired_token(monkeypatch):
    from firebase_admin import auth

    from app.core.security import verify_firebase_token

    monkeypatch.setattr("app.core.security.initialize_firebase", lambda: {})
    for exc in (
        auth.RevokedIdTokenError("revoked"),
        auth.ExpiredIdTokenError("expired", cause=None),
        auth.UserDisabledError("disabled"),
    ):
        monkeypatch.setattr(auth, "verify_id_token", Mock(side_effect=exc))
        with pytest.raises(APIError) as error:
            verify_firebase_token("Bearer test")
        assert error.value.status == 401
        auth.verify_id_token.assert_called_once_with("test", check_revoked=True)


def test_invalid_cursor_json_structures_are_422():
    import base64

    for raw in [b"[]", b"null", b"1", b"{}", b'{"scope":"x","id":"id","value":null}']:
        with pytest.raises(APIError) as error:
            decode_cursor(base64.urlsafe_b64encode(raw).decode(), "x")
        assert error.value.status == 422


def test_production_configuration_accepts_real_project_without_emulators():
    settings = Settings(
        _env_file=None,
        app_env="production",
        firebase_project_id="real-project",
        firebase_storage_bucket="real-project.appspot.com",
        firebase_auth_emulator_host=None,
        firestore_emulator_host=None,
        storage_emulator_host=None,
        backend_cors_origins=["https://frontend.example.com"],
    )
    assert settings.app_env == "production"


def test_cursor_preserves_firestore_nanoseconds():
    from google.api_core.datetime_helpers import DatetimeWithNanoseconds

    stamp = DatetimeWithNanoseconds(2026, 1, 1, nanosecond=123456789)
    decoded, doc_id = decode_cursor(encode_cursor("scope", stamp, "doc"), "scope")
    assert decoded.nanosecond == 123456789
    assert doc_id == "doc"


def test_rag_route_uses_backend_auth_and_returns_citations(api, repo, monkeypatch):
    from app.core.database import get_database

    client, app, _ = api
    database = Mock()
    row = Mock()
    row.id = "chunk-1"
    row.to_dict.return_value = {
        "document_id": "doc-1",
        "document_title": "Luật mẫu",
        "content": "Điều 1 quy định về hợp đồng.",
        "embedding": [1.0, 0.0],
        "article": "1",
    }
    database.collection.return_value.limit.return_value.stream.return_value = [row]
    app.dependency_overrides[get_database] = lambda: database
    ai = Mock()
    ai.embed.return_value = [[1.0, 0.0]]
    ai.answer.return_value = "Căn cứ Điều 1."
    factory = Mock(return_value=ai)
    monkeypatch.setattr("app.api.v1.rag.OpenAIService", factory)
    monkeypatch.setattr(
        "app.api.v1.rag.get_settings",
        lambda: get_settings().model_copy(update={"openai_api_key": "sk-test-only"}),
    )
    payload = {"question": "Quy định về hợp đồng?", "top_k": 5}
    assert client.post("/api/v1/rag/ask", json=payload).status_code == 401
    factory.assert_not_called()
    identity(app)
    profile(repo)
    repo.rows[("users", "reader")]["isActive"] = False
    assert client.post("/api/v1/rag/ask", json=payload).status_code == 403
    factory.assert_not_called()
    repo.rows[("users", "reader")]["isActive"] = True
    response = client.post("/api/v1/rag/ask", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["citations"][0]["chunk_id"] == "chunk-1"
    assert response.json()["has_sufficient_evidence"] is True
    ai.embed.assert_called_once_with([payload["question"]])
    ai.answer.assert_called_once()


def test_rag_without_api_key_is_503_while_core_backend_still_works(api, repo, monkeypatch):
    from app.core.database import get_database

    client, app, _ = api
    identity(app)
    profile(repo)
    app.dependency_overrides[get_database] = lambda: Mock()
    monkeypatch.setattr(
        "app.api.v1.rag.get_settings",
        lambda: get_settings().model_copy(update={"openai_api_key": ""}),
    )
    response = client.post("/api/v1/rag/ask", json={"question": "Câu hỏi pháp luật"})
    assert response.status_code == 503
    assert response.json()["requestId"]
    assert client.get("/api/v1/users/me").status_code == 200
    assert client.get("/health").status_code == 200
