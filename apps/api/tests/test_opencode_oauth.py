from unittest.mock import Mock

from app.core.config import get_settings
from app.core.database import get_database
from app.schemas.rag import StoredChunk
from app.services import opencode_oauth
from tests.test_backend import api, identity, profile, repo

__all__ = ["api", "repo"]


def test_oauth_routes_are_local_gated_and_bound_to_user(api, repo, monkeypatch):
    client, app, _ = api
    identity(app)
    profile(repo)
    settings = get_settings()
    monkeypatch.setattr(settings, "opencode_chatgpt_local_enabled", False)
    assert client.post("/api/v1/ai/chatgpt/start").status_code == 503
    monkeypatch.setattr(settings, "opencode_chatgpt_local_enabled", True)
    start = Mock(return_value={"url": "https://auth.openai.com/test", "instructions": "code"})
    monkeypatch.setattr(opencode_oauth, "start", start)
    monkeypatch.setattr(opencode_oauth, "get", lambda user_id: {"connected": user_id == "reader"})
    assert client.post("/api/v1/ai/chatgpt/start").status_code == 200
    assert start.call_args.args[0] == "reader"
    assert client.get("/api/v1/ai/chatgpt").json()["connected"] is True
    identity(app, "other")
    profile(repo, "other")
    assert client.get("/api/v1/ai/chatgpt").json()["connected"] is False


def test_chatgpt_rag_uses_personal_oauth_without_api_key_or_fallback(api, repo, monkeypatch):
    client, app, _ = api
    identity(app)
    profile(repo)
    app.dependency_overrides[get_database] = lambda: Mock()
    settings = get_settings()
    monkeypatch.setattr(settings, "opencode_local_enabled", True)
    monkeypatch.setattr(settings, "opencode_chatgpt_local_enabled", True)
    chunk = StoredChunk(id="c", document_id="d", document_title="Luật mẫu", text="Điều 1", score=1)
    monkeypatch.setattr("app.api.v1.rag.retrieve_chunks", Mock(return_value=[chunk]))
    factory = Mock(return_value=Mock(answer=Mock(return_value="Căn cứ Điều 1.")))
    monkeypatch.setattr("app.api.v1.rag.OAuthAnswer", factory)
    resolve = Mock(side_effect=AssertionError("must not use a key"))
    monkeypatch.setattr("app.api.v1.rag.resolve", resolve)
    payload = {
        "question": "Điều 1 quy định gì?",
        "engine": "opencode",
        "provider": "openai",
        "credential_source": "chatgpt",
        "retrieval_mode": "keyword",
        "model": "gpt-5.6-luna",
    }
    response = client.post("/api/v1/rag/ask", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["credential_source"] == "chatgpt"
    assert response.json()["citations"][0]["chunk_id"] == "c"
    factory.assert_called_once_with("reader", "gpt-5.6-luna")
    resolve.assert_not_called()
    assert (
        client.post("/api/v1/rag/ask", json={**payload, "retrieval_mode": "hybrid"}).status_code
        == 422
    )
    assert client.post("/api/v1/rag/ask", json={**payload, "engine": "direct"}).status_code == 422
