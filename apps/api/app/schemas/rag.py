from pydantic import BaseModel, Field


class StoredChunk(BaseModel):
    id: str
    document_id: str
    document_title: str
    text: str
    page_number: int | None = None
    chapter: str | None = None
    article: str | None = None
    clause: str | None = None
    point: str | None = None
    source_url: str | None = None
    score: float = 0.0


class Citation(BaseModel):
    document_title: str
    article: str | None = None
    clause: str | None = None
    point: str | None = None
    page_number: int | None = None
    source_url: str | None = None
    chunk_id: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[StoredChunk]
    has_sufficient_evidence: bool
