from app.core.config import Settings
from app.schemas.rag import AskResponse, Citation, StoredChunk
from app.services.ai import OpenAIService


def make_citations(chunks: list[StoredChunk]) -> list[Citation]:
    return [
        Citation(
            document_title=chunk.document_title,
            article=chunk.article,
            clause=chunk.clause,
            point=chunk.point,
            page_number=chunk.page_number,
            source_url=chunk.source_url,
            chunk_id=chunk.id,
        )
        for chunk in chunks
    ]


def answer_question(
    question: str,
    chunks: list[StoredChunk],
    ai: OpenAIService,
    settings: Settings,
) -> AskResponse:
    sufficient = bool(chunks) and chunks[0].score >= settings.rag_min_retrieval_score
    if not sufficient:
        return AskResponse(
            answer="Chưa tìm thấy đủ căn cứ pháp lý để trả lời câu hỏi này.",
            citations=[],
            retrieved_chunks=chunks,
            has_sufficient_evidence=False,
        )
    answer = ai.answer(question, chunks)
    return AskResponse(
        answer=answer,
        citations=make_citations(chunks),
        retrieved_chunks=chunks,
        has_sufficient_evidence=True,
    )
