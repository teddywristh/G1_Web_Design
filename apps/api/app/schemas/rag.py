from datetime import date
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
    document_version_id: str | None = None
    provision_version_id: str | None = None
    source_type: str | None = None
    quote: str | None = None
    evidence_url: str | None = None


class ClaimCitation(BaseModel):
    claim_id: str
    kind: str
    text: str
    support: str
    chunk_ids: list[str] = []


AnswerStatus = Literal[
    "answered",
    "needs_clarification",
    "insufficient_evidence",
    "conflicting_sources",
    "temporarily_unavailable",
]


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    provider: Provider = "openai"
    credential_source: CredentialSource = "auto"
    model: str | None = Field(
        default=None, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$"
    )
    retrieval_mode: Literal["hybrid", "keyword"] = "hybrid"
    engine: Literal["opencode"] = "opencode"
    public_embedding_input_confirmed: bool = False
    knowledge_base_ids: list[str] | None = Field(default=None, max_length=5)
    as_of: date | None = None
    session_facts: list[str] = Field(default_factory=list, max_length=10)
    web_mode: Literal["off", "official", "examples"] = "off"


class AskResponse(BaseModel):
    engine: Literal["opencode"] = "opencode"
    provider: Provider | None = None
    credential_source: Literal["personal", "shared", "chatgpt"] | None = None
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[StoredChunk]
    has_sufficient_evidence: bool
    status: AnswerStatus = "insufficient_evidence"
    as_of: date | None = None
    assumptions: list[str] = []
    missing_facts: list[str] = []
    claim_citations: list[ClaimCitation] = []
    source_limitations: list[str] = []
    image_query: str | None = None
    run_id: str | None = None
