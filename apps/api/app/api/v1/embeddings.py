"""Authenticated access to the system's local embedding host."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.core.errors import APIError
from app.dependencies import current_user
from app.services.embeddings import LocalEmbedding

router = APIRouter(prefix="/api/v1", tags=["embeddings"])


class EmbeddingInput(BaseModel):
    input: str | list[str] = Field(min_length=1, max_length=32_000)
    input_type: Literal["query", "passage"] = "passage"

    @field_validator("input")
    @classmethod
    def nonblank(cls, value):
        texts = [value] if isinstance(value, str) else value
        if len(texts) > 8 or any(not text.strip() or len(text) > 32000 for text in texts):
            raise ValueError("Supply 1–8 nonblank texts of at most 32000 characters")
        return value


@router.post("/embeddings")
def embeddings(body: EmbeddingInput, user=Depends(current_user)):
    settings = get_settings()
    if settings.embedding_provider != "local":
        raise APIError(503, "feature_disabled", "Local embeddings are not enabled")
    vectors = LocalEmbedding(settings, input_type=body.input_type).embed(
        [body.input] if isinstance(body.input, str) else body.input
    )
    return {
        "object": "list",
        "model": settings.local_embedding_model,
        "data": [
            {"object": "embedding", "index": i, "embedding": vector}
            for i, vector in enumerate(vectors)
        ],
    }
