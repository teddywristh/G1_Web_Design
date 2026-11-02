from unittest.mock import Mock

from app.schemas.rag import AskResponse, Citation


def stub_qa(monkeypatch, use_embedder=False):
    """Route tests check provider and credential selection, not retrieval."""
    response = AskResponse(
        answer="Căn cứ Điều 1.",
        citations=[Citation(document_title="Luật mẫu", chunk_id="c")],
        retrieved_chunks=[],
        has_sufficient_evidence=True,
        status="answered",
    )

    def run(repo, user, request, ai, embedder, settings):
        if use_embedder:
            embedder.embed([request.question])
        return response

    stub = Mock(side_effect=run)
    monkeypatch.setattr("app.api.v1.rag.qa.answer", stub)
    return stub
