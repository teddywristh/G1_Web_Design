import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.errors import APIError
from app.search.base import profile_from
from app.services.embeddings import (
    EmbeddingQuotaWait,
    OpenRouterEmbedding,
    requires_public_input,
    reserve_free_request,
)
from app.workers.ingestion import make_embedder
from tests.memory_repo import MemoryRepo

KEY = "sk-or-test-synthetic-only"


def test_shared_quota_limits_burst_and_rolling_day(monkeypatch):
    repo = MemoryRepo()
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.embeddings.utcnow", lambda: now)
    reserve_free_request(repo, KEY)
    with pytest.raises(EmbeddingQuotaWait) as error:
        reserve_free_request(repo, KEY)
    assert error.value.retry_at == now + timedelta(seconds=5)
    for i in range(1, 40):
        monkeypatch.setattr(
            "app.services.embeddings.utcnow", lambda: now + timedelta(seconds=5 * i)
        )
        reserve_free_request(repo, KEY)
    current = now + timedelta(seconds=200)
    monkeypatch.setattr("app.services.embeddings.utcnow", lambda: current)
    with pytest.raises(EmbeddingQuotaWait) as error:
        reserve_free_request(repo, KEY)
    assert error.value.retry_at == now + timedelta(days=1)
    assert KEY not in str(repo.rows)


@pytest.fixture
def settings():
    return get_settings().model_copy(
        update={
            "embedding_provider": "openrouter",
            "openrouter_embedding_model": "nvidia/nemotron-3.5-embed-1b:free",
            "openrouter_embedding_api_key": SecretStr(KEY),
            "embedding_dimensions": 3,
        }
    )


def test_openrouter_embed_uses_configured_profile_and_orders_results(settings):
    def handler(request):
        assert str(request.url) == "https://openrouter.ai/api/v1/embeddings"
        assert request.headers["authorization"] == "Bearer " + KEY
        body = json.loads(request.content)
        assert body["model"] == settings.openrouter_embedding_model
        assert body["dimensions"] == 3 and body["input_type"] == "search_document"
        return httpx.Response(
            200,
            json={
                "data": [{"index": 1, "embedding": [4, 5, 6]}, {"index": 0, "embedding": [1, 2, 3]}]
            },
        )

    client = OpenRouterEmbedding(
        settings, input_type="search_document", transport=httpx.MockTransport(handler)
    )
    assert client.embed(["first", "second"]) == [[1, 2, 3], [4, 5, 6]]
    assert profile_from(settings).id == "openrouter:nvidia/nemotron-3.5-embed-1b:free:3:v1"
    assert KEY not in repr(settings)


def test_nvidia_free_splits_large_batches_in_order(settings):
    batches = []

    def handler(request):
        inputs = json.loads(request.content)["input"]
        batches.append(len(inputs))
        return httpx.Response(
            200,
            json={
                "data": [{"index": i, "embedding": [int(v), 0, 0]} for i, v in enumerate(inputs)]
            },
        )

    client = OpenRouterEmbedding(
        settings, input_type="search_document", transport=httpx.MockTransport(handler)
    )
    assert [v[0] for v in client.embed([str(i) for i in range(19)])] == list(range(19))
    assert batches == [8, 8, 3]


def test_nvidia_free_splits_batches_by_text_size(settings):
    batches = []

    def handler(request):
        inputs = json.loads(request.content)["input"]
        batches.append(len(inputs))
        return httpx.Response(
            200,
            json={"data": [{"index": i, "embedding": [1, 2, 3]} for i in range(len(inputs))]},
        )

    client = OpenRouterEmbedding(
        settings, input_type="search_document", transport=httpx.MockTransport(handler)
    )
    assert len(client.embed(["a" * 1500, "b" * 1500, "c" * 200])) == 3
    assert batches == [1, 2]


def test_provider_server_error_splits_batch_and_preserves_order(settings):
    sizes = []

    def handler(request):
        inputs = json.loads(request.content)["input"]
        sizes.append(len(inputs))
        if len(inputs) > 1:
            return httpx.Response(502)
        return httpx.Response(
            200, json={"data": [{"index": 0, "embedding": [int(inputs[0]), 0, 0]}]}
        )

    client = OpenRouterEmbedding(
        settings, input_type="search_document", transport=httpx.MockTransport(handler)
    )
    assert [v[0] for v in client.embed(["1", "2", "3"])] == [1, 2, 3]
    assert sizes == [3, 1, 2, 1, 1]


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "ai_not_configured"),
        (402, "ai_not_configured"),
        (429, "ai_rate_limited"),
        (500, "ai_unavailable"),
    ],
)
def test_provider_failures_never_echo_key(settings, status, code):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": KEY}))
    with pytest.raises(APIError) as error:
        OpenRouterEmbedding(settings, input_type="search_query", transport=transport).embed(
            ["test"]
        )
    assert error.value.code == code and KEY not in error.value.message


def test_invalid_vector_response_is_rejected(settings):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})
    )
    with pytest.raises(APIError) as error:
        OpenRouterEmbedding(settings, input_type="search_query", transport=transport).embed(
            ["test"]
        )
    assert error.value.code == "ai_unavailable"


def test_worker_does_not_send_unconfirmed_documents_to_nvidia_free(settings):
    repo = Mock()
    repo.get.return_value = {"id": "u", "isActive": True}
    job = {"ownerUid": "u", "credentialSource": "auto"}
    assert requires_public_input(settings)
    with pytest.raises(APIError) as error:
        make_embedder(repo, settings, job)
    assert error.value.code == "embedding_public_input_required"
    assert isinstance(
        make_embedder(repo, settings, {**job, "publicEmbeddingInputConfirmed": True}),
        OpenRouterEmbedding,
    )
