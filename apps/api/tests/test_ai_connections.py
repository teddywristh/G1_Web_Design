import json
from unittest.mock import Mock

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.errors import APIError
from app.schemas.ai_connections import ConnectionPut
from app.schemas.rag import StoredChunk
from app.services import ai_connections as connections
from app.services.ai import AnthropicService
from tests.stubs import stub_qa

from .test_backend import api as api  # noqa: F401
from .test_backend import identity, profile
from .test_backend import repo as repo  # noqa: F401

PERSONAL = "sk-test-personal-not-a-real-key"
SHARED = "sk-test-shared-not-a-real-key"


@pytest.fixture(autouse=True)
def configured_crypto(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(
        settings, "ai_credential_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "ai_allow_shared_keys", True)
    return settings


def save(repo, user, key=PERSONAL, provider="openai", shared=False, version=0, enabled=True):
    return connections.save(
        repo,
        user,
        provider,
        ConnectionPut(apiKey=key, expectedVersion=version, enabled=enabled),
        get_settings(),
        "test",
        shared=shared,
    )


def test_keys_encrypted_and_never_returned(api, repo):
    client, app, _ = api
    identity(app)
    profile(repo)
    response = client.put(
        "/api/v1/ai/connections/openai", json={"apiKey": PERSONAL, "expectedVersion": 0}
    )
    assert response.status_code == 200, response.text
    assert response.json()["configured"] is True
    assert PERSONAL not in response.text
    row = repo.get("ai_connections", connections.connection_id("user:reader", "openai"))
    assert PERSONAL not in json.dumps(row, default=str)
    assert row["encryptedCredential"]
    all_options = client.get("/api/v1/ai/connections")
    assert PERSONAL not in all_options.text
    assert row["encryptedCredential"] not in all_options.text
    assert (
        connections.resolve(repo, {"id": "reader"}, "openai", "personal", get_settings()).api_key
        == PERSONAL
    )


def test_personal_ownership_and_shared_admin_guard(api, repo):
    client, app, _ = api
    assert client.get("/api/v1/ai/connections").status_code == 401
    identity(app)
    profile(repo)
    assert (
        client.put(
            "/api/v1/admin/ai/connections/openai", json={"apiKey": SHARED, "expectedVersion": 0}
        ).status_code
        == 403
    )
    save(repo, {"id": "reader", "role": "user"})
    identity(app, "other")
    profile(repo, "other")
    items = client.get("/api/v1/ai/connections").json()["connections"]
    assert not next(x for x in items if x["scope"] == "personal" and x["provider"] == "openai")[
        "configured"
    ]
    assert (
        client.delete("/api/v1/ai/connections/openai", headers={"If-Match": "1"}).status_code == 404
    )
    # An owner cannot be injected to address another account's record.
    assert (
        client.put(
            "/api/v1/ai/connections/openai",
            json={"apiKey": PERSONAL, "expectedVersion": 0, "ownerId": "reader"},
        ).status_code
        == 422
    )
    identity(app, "admin")
    profile(repo, "admin", "admin")
    assert (
        client.put(
            "/api/v1/admin/ai/connections/anthropic", json={"apiKey": SHARED, "expectedVersion": 0}
        ).status_code
        == 200
    )


def test_selection_priorities_and_explicit_billing_source(repo):
    reader = {"id": "reader", "role": "user"}
    admin = {"id": "admin", "role": "admin"}
    save(repo, admin, SHARED, shared=True)
    assert connections.resolve(repo, reader, "openai", "auto", get_settings()).api_key == SHARED
    with pytest.raises(APIError):
        connections.resolve(repo, reader, "openai", "personal", get_settings())
    save(repo, reader)
    assert connections.resolve(repo, reader, "openai", "auto", get_settings()).api_key == PERSONAL
    assert connections.resolve(repo, reader, "openai", "shared", get_settings()).api_key == SHARED


def test_connection_version_conflicts_and_delete_tombstone(repo, configured_crypto):
    admin = {"id": "admin", "role": "admin"}
    result = save(repo, admin, SHARED, shared=True)
    with pytest.raises(APIError) as error:
        save(repo, admin, "sk-test-replacement", shared=True)
    assert error.value.status == 409
    configured_crypto.openai_api_key = "sk-test-environment"
    connections.remove(repo, admin, "openai", result.version, get_settings(), "test", shared=True)
    with pytest.raises(APIError):
        connections.resolve(repo, {"id": "reader"}, "openai", "shared", get_settings())


def test_server_shared_policy_and_storage_readiness(repo, configured_crypto):
    configured_crypto.openai_api_key = SHARED
    assert (
        connections.resolve(repo, {"id": "reader"}, "openai", "shared", get_settings()).api_key
        == SHARED
    )
    configured_crypto.ai_allow_shared_keys = False
    with pytest.raises(APIError):
        connections.resolve(repo, {"id": "reader"}, "openai", "shared", get_settings())
    configured_crypto.ai_credential_encryption_key = SecretStr("")
    options = connections.options(repo, {"id": "reader"}, get_settings())
    assert options["credentialStorageReady"] is False
    assert all(not x["available"] for x in options["methods"] if "oauth" in x["id"])
    with pytest.raises(APIError):
        save(repo, {"id": "reader", "role": "user"})


def test_ciphertext_cannot_be_reassigned_to_another_account(repo):
    save(repo, {"id": "reader", "role": "user"})
    row = repo.get("ai_connections", connections.connection_id("user:reader", "openai"))
    repo.rows[("ai_connections", connections.connection_id("user:other", "openai"))] = row
    with pytest.raises(APIError) as error:
        connections.resolve(repo, {"id": "other"}, "openai", "personal", get_settings())
    assert error.value.code == "credential_unavailable"


def test_invalid_key_input_does_not_echo_secret(api, repo):
    client, app, _ = api
    identity(app)
    profile(repo)
    secret = "sk-private with whitespace"
    response = client.put(
        "/api/v1/ai/connections/openai", json={"apiKey": secret, "expectedVersion": 0}
    )
    assert response.status_code == 422
    assert secret not in response.text


def test_anthropic_request_and_safe_provider_errors(configured_crypto):
    recorded = []

    def handler(request):
        recorded.append(request)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "Căn cứ Điều 1."}],
                "stop_reason": "end_turn",
            },
        )

    ai = AnthropicService(
        configured_crypto, PERSONAL, "claude-test-model", httpx.MockTransport(handler)
    )
    chunk = StoredChunk(id="c", document_id="d", document_title="Luật mẫu", text="Điều 1", score=1)
    assert ai.answer("Hỏi?", [chunk]) == "Căn cứ Điều 1."
    assert recorded[0].url.host == "api.anthropic.com"
    assert recorded[0].headers["x-api-key"] == PERSONAL
    assert json.loads(recorded[0].content)["model"] == "claude-test-model"
    for status, expected in [(401, 502), (429, 429), (500, 502)]:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": PERSONAL})
        )
        with pytest.raises(APIError) as error:
            AnthropicService(configured_crypto, PERSONAL, "claude-test-model", transport).answer(
                "Hỏi?", [chunk]
            )
        assert error.value.status == expected
        assert PERSONAL not in error.value.message


def test_personal_provider_rejection_never_switches_to_shared(api, repo, monkeypatch):
    from app.core.database import get_database

    client, app, _ = api
    identity(app)
    profile(repo)
    save(repo, {"id": "reader", "role": "user"})
    save(repo, {"id": "admin", "role": "admin"}, SHARED, shared=True)
    app.dependency_overrides[get_database] = lambda: Mock()
    error = Exception("provider echoed " + PERSONAL)
    error.status_code = 401
    factory = Mock(return_value=Mock(embed=Mock(side_effect=error)))
    monkeypatch.setattr("app.api.v1.rag.OpenAIService", factory)
    stub_qa(monkeypatch, use_embedder=True)
    response = client.post("/api/v1/rag/ask", json={"question": "Câu hỏi pháp luật"})
    assert response.status_code == 502
    assert PERSONAL not in response.text
    assert factory.call_count == 1
    assert factory.call_args.args[0].openai_api_key == PERSONAL


def test_claude_keyword_mode_requires_no_openai_embedding_key(api, repo, monkeypatch):
    from app.core.database import get_database

    client, app, _ = api
    identity(app)
    profile(repo)
    save(repo, {"id": "reader", "role": "user"}, provider="anthropic")
    app.dependency_overrides[get_database] = lambda: Mock()
    retrieve = stub_qa(monkeypatch)
    monkeypatch.setattr(
        "app.api.v1.rag.AnthropicService",
        Mock(return_value=Mock(answer=Mock(return_value="Điều 1."))),
    )
    response = client.post(
        "/api/v1/rag/ask",
        json={
            "question": "Câu hỏi pháp luật",
            "provider": "anthropic",
            "credential_source": "personal",
            "retrieval_mode": "keyword",
            "model": "claude-test-model",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "anthropic"
    assert response.json()["credential_source"] == "personal"
    assert retrieve.call_args.args[4] is None


def test_openai_answers_have_bounded_output_and_reject_partial_results(configured_crypto):
    from app.services.ai import OpenAIService

    client = Mock()
    choice = Mock(finish_reason="stop")
    choice.message.content = "Điều 1."
    client.chat.completions.create.return_value.choices = [choice]
    ai = OpenAIService(configured_crypto, client=client)
    assert ai.answer("Câu hỏi", []) == "Điều 1."
    assert (
        client.chat.completions.create.call_args.kwargs["max_completion_tokens"]
        == configured_crypto.ai_max_output_tokens
    )
    choice.finish_reason = "length"
    with pytest.raises(APIError) as error:
        ai.answer("Câu hỏi", [])
    assert error.value.code == "ai_incomplete"


def test_openai_sdk_http_contract_without_external_requests(configured_crypto):
    from openai import OpenAI

    from app.services.ai import OpenAIService

    received = []

    def handle(request):
        received.append(request)
        assert request.headers["authorization"] == "Bearer " + PERSONAL
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [{"index": 0, "object": "embedding", "embedding": [1.0, 0.0]}],
                    "model": "test",
                    "usage": {"prompt_tokens": 1, "total_tokens": 1},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1,
                "model": "test",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Điều 1."},
                    }
                ],
            },
        )

    with OpenAI(
        api_key=PERSONAL,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    ) as client:
        service = OpenAIService(configured_crypto, client=client)
        assert service.embed(["Câu hỏi"]) == [[1.0, 0.0]]
        assert service.answer("Câu hỏi", []) == "Điều 1."
    assert len(received) == 2
    assert all(request.url.host == "api.openai.com" for request in received)
    assert (
        json.loads(received[1].content)["max_completion_tokens"]
        == configured_crypto.ai_max_output_tokens
    )
