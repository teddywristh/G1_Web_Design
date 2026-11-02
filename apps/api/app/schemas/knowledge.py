from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas import Input


class KnowledgeBaseCreate(Input):
    title: str = Field(min_length=1, max_length=200)


class KnowledgeDocumentCreate(Input):
    displayTitle: str = Field(min_length=1, max_length=300)
    sourceUrl: HttpUrl | None = None


class PublishRequest(Input):
    generationId: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9]+$")


class ProvisionReview(Input):
    validFrom: date | None = None
    validUntil: date | None = None
    endKind: Literal["known_end", "open", "unknown"] | None = None
    validityReviewState: Literal["unknown", "reviewed", "conflict"] | None = None
    applicabilityNotes: str | None = Field(default=None, max_length=2000)
    relationRefs: list[dict] | None = Field(default=None, max_length=50)


class Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class KnowledgeBaseOut(Out):
    id: str
    kind: Literal["shared", "private"]
    title: str
    state: str
    ready: bool = False
    activeIndexGeneration: str | None = None
    latestGeneration: str | None = None
    version: int


class KnowledgeDocumentOut(Out):
    id: str
    kbId: str
    displayTitle: str
    sourceUrl: str | None = None
    fileState: str
    fileSize: int | None = None
    trust: str
    createdAt: datetime
    updatedAt: datetime
    deletedAt: datetime | None = None
    version: int


class KnowledgeDocumentPage(Out):
    items: list[KnowledgeDocumentOut]
    nextCursor: str | None


class ProcessingOut(Out):
    status: str
    stage: str
    errorCode: str | None = None
    retryable: bool = False
    nextAction: str | None = None
    warnings: list[str] = []
    legalValidity: str = "unknown"


class EvidenceOut(Out):
    id: str
    kbId: str
    documentId: str
    documentVersionId: str
    provisionVersionId: str
    documentTitle: str
    documentNumber: str
    identifier: str
    chapter: str | None = None
    article: str | None = None
    clause: str | None = None
    text: str
    pageStart: int
    pageEnd: int
    sourceType: str
    sourceUrl: str | None = None
    validFrom: str | None = None
    validUntil: str | None = None
    endKind: str
    validityReviewState: str
    limitations: list[str] = []
