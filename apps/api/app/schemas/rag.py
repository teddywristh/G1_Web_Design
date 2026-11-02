from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ai_connections import CredentialSource, Provider


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
    provider: Provider = "openai"
    credential_source: CredentialSource = "auto"
    model: str | None = Field(
        default=None, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$"
    )
    retrieval_mode: Literal["hybrid", "keyword"] = "hybrid"
    engine: Literal["direct", "opencode"] = "direct"


class AskResponse(BaseModel):
    engine: Literal["direct", "opencode"] = "direct"
    provider: Provider | None = None
    credential_source: Literal["personal", "shared", "chatgpt"] | None = None
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[StoredChunk]
    has_sufficient_evidence: bool
