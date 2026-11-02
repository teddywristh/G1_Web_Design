import math
import re
from collections.abc import Sequence
from typing import Any

from app.schemas.rag import StoredChunk


def _cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    if len(first) != len(second) or not first:
        return 0.0
    first_length = math.sqrt(sum(value * value for value in first))
    second_length = math.sqrt(sum(value * value for value in second))
    if not first_length or not second_length:
        return 0.0
    return sum(a * b for a, b in zip(first, second)) / (first_length * second_length)


def _text_score(query: str, content: str) -> float:
    query_words = set(re.findall(r"\w+", query.casefold()))
    content_words = set(re.findall(r"\w+", content.casefold()))
    if not query_words:
        return 0.0
    return len(query_words & content_words) / len(query_words)


def retrieve_chunks(
    database: Any,
    query_embedding: list[float] | None,
    query_text: str,
    top_k: int,
) -> list[StoredChunk]:
    """Read existing chunks from Firestore and rank them in the API."""
    rows = database.collection("document_chunks").limit(100).stream()
    chunks: list[StoredChunk] = []
    for row in rows:
        data = row.to_dict() or {}
        content = str(data.get("content") or data.get("text") or "").strip()
        if not content:
            continue
        text_score = _text_score(query_text, content)
        if query_embedding is None:
            score = text_score
        else:
            vector_score = _cosine_similarity(query_embedding, data.get("embedding", []))
            score = 0.8 * vector_score + 0.2 * text_score
        chunks.append(
            StoredChunk(
                id=row.id,
                document_id=str(data.get("document_id", "")),
                document_title=str(data.get("document_title", "Tài liệu pháp luật")),
                text=content,
                page_number=data.get("page_number"),
                chapter=data.get("chapter"),
                article=data.get("article"),
                clause=data.get("clause"),
                point=data.get("point"),
                source_url=data.get("source_url"),
                score=score,
            )
        )
    chunks.sort(key=lambda chunk: chunk.score, reverse=True)
    return chunks[:top_k]
