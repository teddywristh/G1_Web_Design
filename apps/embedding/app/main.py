"""Nemotron text embeddings. Run one worker per GPU."""

import hmac
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

MODEL = "nvidia/Nemotron-3.5-Embed-1B-BF16"
ROOT = Path(__file__).resolve().parents[3]
logger = logging.getLogger("uvicorn.error")


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = MODEL
    input: str | list[str] = Field(min_length=1, max_length=100000)
    input_type: Literal["query", "passage"] = "passage"
    dimensions: int = Field(default=1536, ge=1, le=2048)

    @field_validator("input")
    @classmethod
    def validate_text(cls, value):
        texts = [value] if isinstance(value, str) else value
        if len(texts) > 32 or any(not t.strip() or len(t) > 100000 for t in texts):
            raise ValueError(
                "Supply 1–32 nonblank texts, each at most 100000 characters"
            )
        return value


class Runtime:
    def __init__(self):
        self.model = None
        self.torch = None
        self.lock = threading.Lock()
        self.failure = None

    def load(self):
        try:
            import torch
            from sentence_transformers import SentenceTransformer

            self.torch = torch
            device = os.getenv("EMBEDDING_DEVICE", "cuda")
            if device.startswith("cuda") and not torch.cuda.is_available():
                raise RuntimeError("CUDA unavailable")
            dtype = os.getenv("EMBEDDING_DTYPE", "bfloat16")
            if dtype not in {"bfloat16", "float16", "float32"}:
                raise ValueError("Unsupported dtype")
            self.model = SentenceTransformer(
                os.getenv(
                    "EMBEDDING_MODEL_PATH", str(ROOT / "models/nemotron-3.5-embed-1b")
                ),
                device=device,
                local_files_only=True,
                model_kwargs={
                    "dtype": getattr(torch, dtype),
                    "attn_implementation": "sdpa",
                },
            )
            self.model.max_seq_length = int(os.getenv("EMBEDDING_MAX_LENGTH", "512"))
        except Exception as exc:  # noqa: BLE001 - keep host alive and redact model errors
            self.model = None
            self.failure = type(exc).__name__
            logger.error(
                "Embedding model unavailable (%s); check runtime, CUDA and model path",
                self.failure,
            )

    def encode(self, body):
        if self.model is None:
            raise HTTPException(503, "Model unavailable; inspect service logs")
        if not self.lock.acquire(blocking=False):
            raise HTTPException(
                429, "Inference busy; retry later", headers={"Retry-After": "1"}
            )
        started = time.monotonic()
        texts = [body.input] if isinstance(body.input, str) else body.input
        try:
            encode = (
                self.model.encode_query
                if body.input_type == "query"
                else self.model.encode_document
            )
            values = np.asarray(
                encode(
                    texts, batch_size=1, convert_to_numpy=True, show_progress_bar=False
                ),
                dtype=np.float32,
            )
            if (
                values.ndim != 2
                or values.shape[0] != len(texts)
                or values.shape[1] < body.dimensions
            ):
                raise RuntimeError("Invalid embedding shape")
            values = values[:, : body.dimensions]
            norms = np.linalg.norm(values, axis=1, keepdims=True)
            if (
                not np.isfinite(values).all()
                or not np.isfinite(norms).all()
                or (norms == 0).any()
            ):
                raise RuntimeError("Invalid embedding values")
            values = values / norms
            return {
                "object": "list",
                "model": MODEL,
                "data": [
                    {"object": "embedding", "index": i, "embedding": row.tolist()}
                    for i, row in enumerate(values)
                ],
            }
        except Exception as exc:  # noqa: BLE001 - keep host alive and redact model errors
            if self.torch is not None and isinstance(
                exc, self.torch.cuda.OutOfMemoryError
            ):
                self.torch.cuda.empty_cache()
                raise HTTPException(
                    503,
                    "GPU out of memory; shorten input",
                    headers={"Retry-After": "1"},
                ) from None
            logger.error("Embedding inference failed (%s)", type(exc).__name__)
            raise HTTPException(503, "Embedding inference failed") from None
        finally:
            gpu_bytes = 0
            if self.torch is not None and self.torch.cuda.is_available():
                gpu_bytes = self.torch.cuda.max_memory_allocated()
            logger.info(
                "embedding count=%d duration_ms=%d gpu_peak_bytes=%d",
                len(texts),
                (time.monotonic() - started) * 1000,
                gpu_bytes,
            )
            self.lock.release()


def create_app(runtime=None):
    runtime = runtime or Runtime()

    @asynccontextmanager
    async def lifespan(app):
        runtime.load()
        yield
        runtime.model = None

    api = FastAPI(title="Local Nemotron Embedding Host", lifespan=lifespan)

    @api.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(
            status_code=422, content={"detail": "Invalid embedding request"}
        )

    @api.middleware("http")
    async def limit_body(request: Request, call_next):
        if request.method == "POST":
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 1024 * 1024:
                    return JSONResponse(
                        status_code=413, content={"detail": "Body exceeds 1 MiB"}
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
        return await call_next(request)

    def authorize(authorization: str = Header(default="")):
        key = os.getenv("EMBEDDING_API_KEY", "")
        if key and not hmac.compare_digest(authorization, f"Bearer {key}"):
            raise HTTPException(
                401, "Invalid API key", headers={"WWW-Authenticate": "Bearer"}
            )

    @api.get("/health")
    def health():
        return {
            "status": "ok",
            "model_loaded": runtime.model is not None,
            "model": MODEL,
        }

    @api.get("/ready")
    def ready():
        if runtime.model is None:
            raise HTTPException(503, "Model unavailable")
        return {"status": "ready", "model": MODEL}

    @api.post("/v1/embeddings", dependencies=[Depends(authorize)])
    def embeddings(body: EmbeddingRequest):
        if body.model != MODEL:
            raise HTTPException(400, "Unknown model")
        return runtime.encode(body)

    return api


app = create_app()
