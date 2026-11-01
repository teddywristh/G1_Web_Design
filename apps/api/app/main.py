from fastapi import FastAPI

from app.api.v1.rag import router as rag_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(rag_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}
