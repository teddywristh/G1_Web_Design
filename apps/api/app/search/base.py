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
    if settings.embedding_provider == "local":
        return EmbeddingProfile(
            "local",
            settings.local_embedding_model,
            settings.embedding_dimensions,
            settings.local_embedding_profile_version,
        )
    if settings.embedding_provider == "openrouter":
        return EmbeddingProfile(
            "openrouter", settings.openrouter_embedding_model, settings.embedding_dimensions
        )
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
