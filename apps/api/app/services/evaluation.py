from dataclasses import dataclass

from app.schemas.rag import Citation, StoredChunk


@dataclass
class EvaluationResult:
    retrieval_relevance: float
    citation_accuracy: float
    answer_grounded: bool


def evaluate_result(
    answer: str,
    chunks: list[StoredChunk],
    citations: list[Citation],
    expected_terms: set[str],
) -> EvaluationResult:
    answer_text = answer.casefold()
    matched_terms = sum(term.casefold() in answer_text for term in expected_terms)
    relevance = matched_terms / len(expected_terms) if expected_terms else 0.0
    valid_chunk_ids = {chunk.id for chunk in chunks}
    valid_citations = sum(
        citation.chunk_id in valid_chunk_ids for citation in citations
    )
    citation_accuracy = valid_citations / len(citations) if citations else 0.0
    grounded = bool(chunks) and citation_accuracy == 1.0 and relevance > 0
    return EvaluationResult(relevance, citation_accuracy, grounded)
