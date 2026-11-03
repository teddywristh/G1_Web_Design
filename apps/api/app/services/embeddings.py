"""Embedding adapter for the separately configured system OpenRouter key."""

import hashlib
import logging
import math
from datetime import timedelta
from uuid import uuid4

import httpx

from app.core.errors import APIError
from app.repositories.backend import utcnow

logger = logging.getLogger("legal_api")


class EmbeddingQuotaWait(APIError):
    def __init__(self, retry_at):
        super().__init__(429, "embedding_quota_wait", "Embedding quota is temporarily reserved")
        self.retry_at = retry_at


def reserve_free_request(repo, key):
    """Coordinate a conservative rolling quota across workers sharing this key."""
    now = utcnow()
    reservation = uuid4().hex
    scope = hashlib.sha256(key.encode()).hexdigest()

    def reserve(current):
        recent = sorted(
            t for t in (current or {}).get("requests", []) if t > now - timedelta(days=1)
        )
        if (recent and recent[-1] + timedelta(seconds=5) > now) or len(recent) >= 40:
            return None
        return {"requests": recent + [now], "reservation": reservation}

    row = repo.mutate(
        "embedding_quotas",
        scope,
        reserve,
        actor="system",
        event="embedding.reserve",
        request_id=reservation,
    )
    if row.get("reservation") == reservation:
        return
    recent = sorted(t for t in row.get("requests", []) if t > now - timedelta(days=1))
    retry_at = recent[-1] + timedelta(seconds=5) if recent else now + timedelta(seconds=5)
    if len(recent) >= 40:
        retry_at = max(retry_at, recent[0] + timedelta(days=1))
    raise EmbeddingQuotaWait(retry_at)


def requires_public_input(settings):
    """NVIDIA's free endpoints prohibit confidential information and personal data."""
    return (
        settings.embedding_provider == "openrouter"
        and settings.openrouter_embedding_model.startswith("nvidia/")
        and settings.openrouter_embedding_model.endswith(":free")
    )


class OpenRouterEmbedding:
    def __init__(self, settings, *, input_type, transport=None, repo=None):
        self.settings = settings
        self.input_type = input_type
        self.transport = transport
        self.repo = repo

    def embed(self, texts):
        texts = list(texts)
        # The NVIDIA free endpoint can reject batches with too many inputs or
        # too much text. Split conservatively, keeping original order.
        if requires_public_input(self.settings) and len(texts) > 1:
            batches, batch, size = [], [], 0
            for text in texts:
                if batch and (len(batch) >= 8 or size + len(text) > 2000):
                    batches.append(batch)
                    batch, size = [], 0
                batch.append(text)
                size += len(text)
            if batch:
                batches.append(batch)
            if len(batches) > 1:
                return [vector for batch in batches for vector in self.embed(batch)]
        key = self.settings.openrouter_embedding_api_key.get_secret_value()
        model = self.settings.openrouter_embedding_model
        if not key or not model:
            raise APIError(503, "ai_not_configured", "OpenRouter embedding is not configured")
        if self.repo is not None and model.endswith(":free"):
            reserve_free_request(self.repo, key)
        try:
            with httpx.Client(
                timeout=self.settings.ai_request_timeout_seconds, transport=self.transport
            ) as client:
                response = client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={"Authorization": "Bearer " + key},
                    json={
                        "model": model,
                        "input": list(texts),
                        "dimensions": self.settings.embedding_dimensions,
                        "input_type": self.input_type,
                    },
                )
            if response.status_code in (401, 402, 403):
                raise APIError(
                    503, "ai_not_configured", "OpenRouter embedding key or credits unavailable"
                )
            if response.status_code == 429:
                raise APIError(429, "ai_rate_limited", "OpenRouter embedding rate limit reached")
            if response.status_code >= 500 and len(texts) > 1:
                midpoint = len(texts) // 2
                return self.embed(texts[:midpoint]) + self.embed(texts[midpoint:])
            if response.is_error:
                logger.warning(
                    "embedding_http_error status=%s inputs=%s", response.status_code, len(texts)
                )
            response.raise_for_status()
            data = response.json()["data"]
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError("invalid response")
            ordered = sorted(data, key=lambda item: item["index"])
            if [item["index"] for item in ordered] != list(range(len(texts))):
                raise ValueError("invalid order")
            vectors = [item["embedding"] for item in ordered]
            if any(
                not isinstance(v, list)
                or len(v) != self.settings.embedding_dimensions
                or not all(
                    isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)
                    for n in v
                )
                for v in vectors
            ):
                raise ValueError("invalid vector")
            return vectors
        except APIError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning(
                "embedding_request_failed reason=%s inputs=%s", type(exc).__name__, len(texts)
            )
            raise APIError(503, "ai_unavailable", "OpenRouter embedding request failed") from None
