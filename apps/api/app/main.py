"""Backend entry point with authenticated document and RAG routes."""

import json
import logging
import re
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from firebase_admin.exceptions import FirebaseError
from google.api_core.exceptions import GoogleAPICallError
from starlette.exceptions import HTTPException

from app.api.v1.ai_connections import router as ai_connections_router
from app.api.v1.rag import router as rag_router
from app.api.v1.routes import router
from app.core.config import get_settings
from app.core.errors import APIError
from app.core.firebase import initialize_firebase
from app.dependencies import current_user

logger = logging.getLogger("legal_api")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def create_app():
    settings = get_settings()  # validates production configuration before accepting traffic
    api = FastAPI(title=settings.app_name, version="1.0.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "If-Match", "X-Request-ID"],
        expose_headers=["ETag", "X-Request-ID", "Location"],
    )

    def error(request, status, code, message):
        request_id = getattr(request.state, "request_id", uuid4().hex)
        headers = {"X-Request-ID": request_id, "Cache-Control": "no-store"}
        if status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message}, "requestId": request_id},
            headers=headers,
        )

    @api.exception_handler(APIError)
    async def domain_error(request, exc):
        return error(request, exc.status, exc.code, exc.message)

    @api.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo input values: validation payloads can contain private data.
        fields = ", ".join(".".join(map(str, item["loc"])) for item in exc.errors())
        return error(request, 422, "validation_error", f"Invalid request fields: {fields}")

    @api.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(request, exc.status_code, "http_error", str(exc.detail))

    @api.exception_handler(GoogleAPICallError)
    @api.exception_handler(FirebaseError)
    async def provider_error(request, exc):
        logger.warning(
            json.dumps(
                {
                    "event": "provider_error",
                    "requestId": request.state.request_id,
                    "type": type(exc).__name__,
                }
            )
        )
        return error(request, 503, "provider_unavailable", "A required service is unavailable")

    @api.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error(
            json.dumps(
                {
                    "event": "unhandled_error",
                    "requestId": getattr(request.state, "request_id", ""),
                    "type": type(exc).__name__,
                }
            )
        )
        return error(request, 500, "internal_error", "An unexpected error occurred")

    @api.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request.state.request_id = (
            supplied if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied) else uuid4().hex
        )
        started = time.monotonic()
        # Small JSON bodies are bounded before Pydantic parsing. PDF uses streaming limit.
        if request.method in {"POST", "PUT", "PATCH"} and not request.url.path.endswith("/file"):
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 1024 * 1024:
                    return error(request, 413, "body_too_large", "Request body exceeds 1 MiB")
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "requestId": request.state.request_id,
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", "unmatched"),
                    "status": response.status_code,
                    "durationMs": round((time.monotonic() - started) * 1000),
                }
            )
        )
        return response

    @api.get("/health", tags=["system"])
    def health():
        return {"status": "ok"}

    @api.get("/ready", tags=["system"])
    def ready():
        try:
            clients = initialize_firebase()
            clients["db"].collection("_health").document("readiness").get(timeout=2, retry=None)
            # Object listing works on an empty bucket and the Storage Emulator,
            # unlike the bucket-management endpoint, which the emulator omits.
            objects = clients["storage"].list_blobs(
                max_results=1, page_size=1, timeout=2, retry=None
            )
            next(iter(objects), None)
        except Exception:
            raise APIError(503, "not_ready", "Dependencies are unavailable") from None
        return {"status": "ready"}

    api.include_router(router)
    api.include_router(ai_connections_router)
    api.include_router(rag_router, prefix="/api/v1", dependencies=[Depends(current_user)])
    return api


app = create_app()
