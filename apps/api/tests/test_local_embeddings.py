import json

import httpx
import pytest

from app.core.config import get_settings
from app.core.errors import APIError
from app.search.base import profile_from
from app.services.embeddings import LocalEmbedding, requires_public_input
from app.workers.ingestion import make_embedder
from tests.memory_repo import MemoryRepo


def settings():
    return get_settings().model_copy(
        update={"embedding_provider": "local", "embedding_dimensions": 3}
    )


def test_local_adapter_profile_prompts_and_no_provider_quota():
    config = settings()
    received = []

    def handler(request):
        body = json.loads(request.content)
        received.append(body)
        assert str(request.url) == "http://127.0.0.1:8010/v1/embeddings"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "model": config.local_embedding_model,
                "data": [{"index": 0, "embedding": [0.6, 0.8, 0.0]}],
            },
        )

    adapter = LocalEmbedding(
        config, input_type="search_document", transport=httpx.MockTransport(handler)
    )
    assert adapter.embed(["first", "second"]) == [[0.6, 0.8, 0.0]] * 2
    assert [x["input"] for x in received] == [["first"], ["second"]]
    assert all(x["input_type"] == "passage" for x in received)
    assert not requires_public_input(config)
    assert profile_from(config).id.startswith("local:nvidia/Nemotron-3.5-Embed-1B-BF16:3:")
    repo = MemoryRepo()
    repo.put("users", "alice", {"isActive": True})
    assert isinstance(make_embedder(repo, config, {"ownerUid": "alice"}), LocalEmbedding)


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [{"index": 0, "embedding": [1, 0]}]},
        {"data": [{"index": 1, "embedding": [1, 0, 0]}]},
        {"data": [{"index": 0, "embedding": [1, 1, 1]}]},
        {"data": [{"index": 0, "embedding": [True, 0, 0]}]},
    ],
)
def test_local_adapter_rejects_incompatible_output(payload):
    config = settings()
    payload["model"] = config.local_embedding_model
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    with pytest.raises(APIError):
        LocalEmbedding(config, input_type="query", transport=transport).embed(["x"])


def test_busy_is_short_retry_failure_not_openrouter_quota():
    transport = httpx.MockTransport(lambda _: httpx.Response(429))
    with pytest.raises(APIError) as error:
        LocalEmbedding(settings(), input_type="query", transport=transport).embed(["x"])
    assert error.value.code == "embedding_busy"


def test_authenticated_embedding_route_uses_local_adapter(monkeypatch):
    from fastapi.testclient import TestClient

    from app.dependencies import current_user
    from app.main import create_app

    config = settings()
    monkeypatch.setattr("app.api.v1.embeddings.get_settings", lambda: config)
    calls = []

    def embed(self, texts):
        calls.append((self.input_type, texts))
        return [[0.6, 0.8, 0.0] for _ in texts]

    monkeypatch.setattr(LocalEmbedding, "embed", embed)
    app = create_app()
    with TestClient(app) as client:
        assert client.post("/api/v1/embeddings", json={"input": "test"}).status_code == 401
        app.dependency_overrides[current_user] = lambda: {"id": "alice"}
        response = client.post("/api/v1/embeddings", json={"input": "test", "input_type": "query"})
        assert response.status_code == 200
        assert response.json()["data"][0]["embedding"] == [0.6, 0.8, 0.0]
        assert calls == [("query", ["test"])]
        assert client.post("/api/v1/embeddings", json={"input": " "}).status_code == 422
