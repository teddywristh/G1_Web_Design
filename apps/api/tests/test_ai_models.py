from unittest.mock import Mock

import httpx
import pytest

from app.core.errors import APIError
from app.services import ai_models
from app.services.opencode import worker_access
from tests.test_ai_connections import PERSONAL, SHARED, configured_crypto, save
from tests.test_backend import api, identity, profile, repo

# Import fixtures used by FastAPI dependency overrides.
__all__ = ["api", "repo", "configured_crypto"]


@pytest.fixture(autouse=True)
def empty_cache():
    ai_models.CACHE.clear()


def test_worker_access_allows_remote_clients_only_when_hosted(configured_crypto):
    settings = configured_crypto.model_copy(
        update={
            "app_env": "development",
            "opencode_local_enabled": True,
            "opencode_chatgpt_local_enabled": False,
            "opencode_chatgpt_hosted_enabled": False,
        }
    )
    worker_access(settings, "127.0.0.1", chatgpt=False)
    with pytest.raises(APIError) as error:
        worker_access(settings, "203.0.113.9", chatgpt=False)
    assert error.value.status == 403
    hosted = settings.model_copy(
        update={"opencode_local_enabled": False, "opencode_api_keys_hosted_enabled": True}
    )
    worker_access(hosted, "203.0.113.9", chatgpt=False)
    with pytest.raises(APIError) as error:
        worker_access(hosted, "203.0.113.9", chatgpt=True)
    assert error.value.code == "opencode_unavailable"


def test_openai_listing_keeps_chat_models_newest_first(configured_crypto):
    recorded = []

    def handler(request):
        recorded.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-4o-mini", "created": 1},
                    {"id": "text-embedding-3-small", "created": 9},
                    {"id": "gpt-4o-realtime-preview", "created": 8},
                    {"id": "o3", "created": 5},
                    {"id": "dall-e-3", "created": 7},
                    {"id": "bad id", "created": 6},
                ]
            },
        )

    models = ai_models.fetch("openai", PERSONAL, configured_crypto, httpx.MockTransport(handler))
    assert [item["id"] for item in models] == ["o3", "gpt-4o-mini"]
    assert recorded[0].headers["authorization"] == "Bearer " + PERSONAL


def test_anthropic_listing_uses_api_key_header_and_display_names(configured_crypto):
    recorded = []

    def handler(request):
        recorded.append(request)
        return httpx.Response(
            200, json={"data": [{"id": "claude-test", "display_name": "Claude Test"}]}
        )

    models = ai_models.fetch("anthropic", PERSONAL, configured_crypto, httpx.MockTransport(handler))
    assert models == [{"id": "claude-test", "name": "Claude Test"}]
    assert recorded[0].headers["x-api-key"] == PERSONAL
    assert "authorization" not in recorded[0].headers


def test_listing_errors_never_echo_the_key(configured_crypto):
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={"key": PERSONAL}))
    with pytest.raises(APIError) as error:
        ai_models.fetch("deepseek", PERSONAL, configured_crypto, transport)
    assert error.value.code == "ai_authentication_failed"
    assert PERSONAL not in error.value.message


def test_models_route_groups_configured_connections(api, repo, monkeypatch, configured_crypto):
    client, app, _ = api
    identity(app)
    profile(repo)
    save(repo, {"id": "reader", "role": "user"}, provider="anthropic")
    save(repo, {"id": "admin", "role": "admin"}, SHARED, provider="openrouter", shared=True)
    monkeypatch.setattr(configured_crypto, "opencode_local_enabled", True)
    monkeypatch.setattr(configured_crypto, "opencode_chatgpt_local_enabled", True)
    monkeypatch.setattr(configured_crypto, "opencode_binary", "/test/opencode")
    monkeypatch.setattr(ai_models.opencode_oauth, "get", lambda *_: {"connected": True})
    monkeypatch.setattr(
        ai_models.opencode_oauth, "models", lambda *_: [{"id": "gpt-5.6-luna", "name": "Luna"}]
    )

    def fetch(provider, key, settings, transport=None):
        if provider == "openrouter":
            raise APIError(503, "ai_unavailable", "down")
        return [{"id": f"{provider}-model", "name": key[:7]}]

    fetcher = Mock(side_effect=fetch)
    monkeypatch.setattr(ai_models, "fetch", fetcher)
    response = client.get("/api/v1/ai/models")
    assert response.status_code == 200, response.text
    groups = {item["id"]: item for item in response.json()["groups"]}
    assert list(groups) == ["chatgpt", "anthropic", "openrouter"]
    assert groups["chatgpt"]["source"] == "chatgpt"
    assert groups["chatgpt"]["models"] == [{"id": "gpt-5.6-luna", "name": "Luna"}]
    assert groups["anthropic"]["source"] == "personal"
    assert groups["anthropic"]["models"][0]["id"] == "anthropic-model"
    assert groups["openrouter"]["source"] == "shared"
    assert groups["openrouter"]["error"] == "ai_unavailable"
    assert PERSONAL not in response.text and SHARED not in response.text
    assert client.get("/api/v1/ai/models").status_code == 200
    # Successful listings are cached; failures are retried.
    assert [call.args[0] for call in fetcher.call_args_list].count("anthropic") == 1
    assert [call.args[0] for call in fetcher.call_args_list].count("openrouter") == 2


def test_models_route_omits_api_keys_without_an_opencode_worker(
    api, repo, monkeypatch, configured_crypto
):
    client, app, _ = api
    identity(app)
    profile(repo)
    save(repo, {"id": "reader", "role": "user"})
    monkeypatch.setattr(configured_crypto, "opencode_local_enabled", False)
    monkeypatch.setattr(configured_crypto, "opencode_api_keys_hosted_enabled", False)
    monkeypatch.setattr(configured_crypto, "opencode_chatgpt_local_enabled", False)
    monkeypatch.setattr(configured_crypto, "opencode_chatgpt_hosted_enabled", False)
    monkeypatch.setattr(ai_models, "fetch", Mock(side_effect=AssertionError("must not list")))
    response = client.get("/api/v1/ai/models")
    assert response.json() == {"groups": [], "apiKeysAvailable": False}
