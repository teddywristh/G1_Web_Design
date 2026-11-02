from dataclasses import dataclass
from datetime import date


@dataclass
class EmbeddingProfile:
    provider: str
    model: str
    dimensions: int
    version: str = "v1"  # normalization and input-format version

    @property
    def id(self):
        return f"{self.provider}:{self.model}:{self.dimensions}:{self.version}"


def profile_from(settings):
    return EmbeddingProfile(
        "openai", settings.default_embedding_model, settings.embedding_dimensions
    )


@dataclass
class SearchRequest:
    query: str
    kbs: list  # [{"id": ..., "generation": ...}] already authorized by the server
    as_of: date
    profile: EmbeddingProfile
    vector: list | None
    candidate_k: int
