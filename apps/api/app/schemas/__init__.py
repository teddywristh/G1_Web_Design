"""Strict public API schemas. Internal fields never pass through responses."""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LegalStatus(str, Enum):
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EFFECTIVE = "effective"
    PARTIALLY_EXPIRED = "partially_expired"
    EXPIRED = "expired"


class DocumentCreate(Input):
    title: str = Field(min_length=1, max_length=300)
    documentNumber: str = Field(min_length=1, max_length=100)
    documentType: str = Field(min_length=1, max_length=80)
    issuingAuthority: str = Field(min_length=1, max_length=200)
    issueDate: date
    effectiveDate: date | None = None
    status: LegalStatus
    sourceUrl: HttpUrl | None = None


class DocumentPatch(Input):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    documentNumber: str | None = Field(default=None, min_length=1, max_length=100)
    documentType: str | None = Field(default=None, min_length=1, max_length=80)
    issuingAuthority: str | None = Field(default=None, min_length=1, max_length=200)
    issueDate: date | None = None
    effectiveDate: date | None = None
    status: LegalStatus | None = None
    sourceUrl: HttpUrl | None = None

    @model_validator(mode="after")
    def valid_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field required")
        for key in self.model_fields_set - {"effectiveDate", "sourceUrl"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self


class ProfilePatch(Input):
    displayName: str = Field(min_length=1, max_length=120)


class UserPatch(Input):
    isActive: bool


class DocumentQuery(Input):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=3000)
    documentNumber: str | None = Field(default=None, min_length=1, max_length=100)
    titlePrefix: str | None = Field(default=None, min_length=1, max_length=200)
    documentType: str | None = Field(default=None, min_length=1, max_length=80)
    issuingAuthority: str | None = Field(default=None, min_length=1, max_length=200)
    status: LegalStatus | None = None
    issueDateFrom: date | None = None
    issueDateTo: date | None = None

    @model_validator(mode="after")
    def query_matrix(self):
        selectors = [
            self.documentNumber,
            self.titlePrefix,
            self.documentType,
            self.issuingAuthority,
            self.status,
            self.issueDateFrom is not None or self.issueDateTo is not None,
        ]
        if sum(bool(s) for s in selectors) > 1:
            raise ValueError(
                "Use one selector: number, title, type, authority, status or date range"
            )
        if self.issueDateFrom and self.issueDateTo and self.issueDateFrom > self.issueDateTo:
            raise ValueError("Invalid date range")
        return self


class Output(BaseModel):
    model_config = ConfigDict(extra="ignore")


class UserOut(Output):
    id: str
    email: str | None = None
    displayName: str
    role: Literal["user", "admin"]
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    version: int


class DocumentOut(Output):
    id: str
    title: str
    documentNumber: str
    documentType: str
    issuingAuthority: str
    issueDate: date
    effectiveDate: date | None = None
    status: LegalStatus
    sourceUrl: str | None = None
    fileState: str
    fileSize: int | None = None
    contentType: str | None = None
    createdAt: datetime
    updatedAt: datetime
    deletedAt: datetime | None = None
    version: int


class AuditOut(Output):
    id: str
    event: str
    actorId: str
    targetId: str
    result: str
    requestId: str
    createdAt: datetime


class DocumentPage(Output):
    items: list[DocumentOut]
    nextCursor: str | None


class UserPage(Output):
    items: list[UserOut]
    nextCursor: str | None


class AuditPage(Output):
    items: list[AuditOut]
    nextCursor: str | None
