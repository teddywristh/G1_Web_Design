import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.config import get_settings
from app.core.errors import APIError
from app.dependencies import current_user, get_repository
from app.schemas.rag import AskRequest, AskResponse
from app.services import images, qa
from app.services.ai import OpenAIService
from app.services.ai_connections import Credential, resolve
from app.services.embeddings import LocalEmbedding, OpenRouterEmbedding, requires_public_input
from app.services.opencode import OpenCodeService, worker_access
from app.services.opencode_oauth import OAuthAnswer

router = APIRouter(prefix="/rag", tags=["rag"])


def openai_settings(settings, credential, model=None):
    return settings.model_copy(
        update={
            "openai_api_key": credential.api_key,
            "default_llm_model": model or settings.default_llm_model,
        }
    )


class NoEmbedding:
    """Semantic search is skipped; QA falls back to number/article lookup and says so."""

    def embed(self, texts):
        raise APIError(503, "ai_not_configured", "No embedding key is available")


@router.post("/ask", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    http_request: Request,
    user=Depends(current_user),
    repo=Depends(get_repository),
) -> AskResponse:
    settings = get_settings()
    if not settings.qa_workflow_enabled:
        raise APIError(503, "feature_disabled", "The legal Q&A workflow is disabled")
    chatgpt = request.credential_source == "chatgpt"
    client = http_request.client.host if http_request.client else None
    worker_access(settings, client, chatgpt=chatgpt)
    if chatgpt:
        if request.provider != "openai":
            raise APIError(422, "invalid_provider", "ChatGPT sign-in serves OpenAI models only")
        selected = Credential("openai", "", "chatgpt")
        ai = OAuthAnswer(user["id"], request.model, repo, settings)
        ai.require_session()
    else:
        if request.provider != "openai" and not request.model:
            raise APIError(422, "invalid_model", "Select a model for this provider")
        selected = resolve(repo, user, request.provider, request.credential_source, settings)
        ai = OpenCodeService(settings, selected.api_key, request.model, provider=request.provider)
    try:
        embedder = None
        kbs, _ = qa.resolve_scope(repo, user, request.knowledge_base_ids, settings)
        if any(kb["generation"] for kb in kbs) and request.retrieval_mode == "hybrid":
            if settings.embedding_provider == "local":
                embedder = LocalEmbedding(settings, input_type="query")
            elif settings.embedding_provider == "openrouter":
                if requires_public_input(settings) and not request.public_embedding_input_confirmed:
                    raise APIError(
                        422,
                        "embedding_public_input_required",
                        "Confirm the question contains no confidential or personal information",
                    )
                embedder = OpenRouterEmbedding(settings, input_type="search_query", repo=repo)
            else:
                # Never silently borrow a shared embedding key when personal-only was selected.
                source = "personal" if chatgpt else request.credential_source
                try:
                    embedding_key = resolve(repo, user, "openai", source, settings)
                    embedder = OpenAIService(openai_settings(settings, embedding_key))
                except APIError as exc:
                    if exc.code != "ai_not_configured":
                        raise
                    embedder = NoEmbedding()
        result = qa.answer(repo, user, request, ai, embedder, settings)
        return result.model_copy(
            update={
                "provider": selected.provider,
                "credential_source": selected.source,
                "engine": request.engine,
            }
        )
    except APIError:
        raise
    except RuntimeError:
        raise APIError(
            503, "ai_not_configured", "The selected AI connection is unavailable"
        ) from None
    except Exception as exc:
        # Provider error strings may echo credentials or content; never forward them.
        logging.getLogger("legal_api").warning(
            "RAG request failed requestId=%s errorType=%s",
            getattr(http_request.state, "request_id", ""),
            type(exc).__name__,
        )
        status = getattr(exc, "status_code", None)
        if status in (401, 403):
            raise APIError(
                502, "ai_authentication_failed", "The AI provider rejected the selected key"
            ) from None
        if status == 429:
            raise APIError(
                429, "ai_rate_limited", "The AI provider usage limit was reached"
            ) from None
        raise APIError(503, "ai_unavailable", "The AI request could not be completed") from None


@router.get("/images")
def image_search(q: str = Query(min_length=1, max_length=200)):
    """Illustrative images for an answer; only scrubbed keywords reach Openverse."""
    if not get_settings().image_search_enabled:
        raise APIError(404, "feature_disabled", "Image search is disabled")
    return {"images": images.search(q)}
