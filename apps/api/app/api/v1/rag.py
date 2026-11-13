import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.errors import APIError
from app.dependencies import current_user, get_repository
from app.schemas.rag import AskRequest, AskResponse
from app.services import qa
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


def translate(exc, http_request):
    """Map any failure to a safe API error; provider error strings may echo credentials."""
    if isinstance(exc, APIError):
        return exc
    if isinstance(exc, RuntimeError):
        return APIError(503, "ai_not_configured", "The selected AI connection is unavailable")
    logging.getLogger("legal_api").warning(
        "RAG request failed requestId=%s errorType=%s",
        getattr(http_request.state, "request_id", ""),
        type(exc).__name__,
    )
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return APIError(
            502, "ai_authentication_failed", "The AI provider rejected the selected key"
        )
    if status == 429:
        return APIError(429, "ai_rate_limited", "The AI provider usage limit was reached")
    return APIError(503, "ai_unavailable", "The AI request could not be completed")


def prepare(request, http_request, user, repo):
    """Everything that can fail before an answer starts: access, credentials, scope, embedder.

    Failures here are plain HTTP errors, for both the JSON and the streaming endpoint.
    """
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
        scope = qa.resolve_scope(repo, user, request.knowledge_base_ids, settings)
        kbs, _ = scope
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
    except Exception as exc:
        raise translate(exc, http_request) from None
    return settings, selected, ai, embedder, scope


def annotate(result, selected, request):
    return result.model_copy(
        update={
            "provider": selected.provider,
            "credential_source": selected.source,
            "engine": request.engine,
        }
    )


@router.post("/ask", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    http_request: Request,
    user=Depends(current_user),
    repo=Depends(get_repository),
) -> AskResponse:
    settings, selected, ai, embedder, scope = prepare(request, http_request, user, repo)
    try:
        result = qa.answer(
            repo,
            user,
            request,
            ai,
            embedder,
            settings,
            scope=scope,
            request_id=getattr(http_request.state, "request_id", None),
        )
    except Exception as exc:
        raise translate(exc, http_request) from None
    return annotate(result, selected, request)


def sse(event):
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/ask/stream")
def ask_stream(
    request: AskRequest,
    http_request: Request,
    user=Depends(current_user),
    repo=Depends(get_repository),
):
    """Same workflow as /ask, as server-sent events.

    Events: stage, sources (evidence found), text (a piece of the answer as the model writes it,
    with its source markers already numbered), reset (discard the text shown so far), done (the
    final, complete AskResponse) and error. The `done` response is authoritative and replaces whatever
    was streamed.
    """
    settings, selected, ai, embedder, scope = prepare(request, http_request, user, repo)

    def events():
        try:
            for event in qa.answer_events(
                repo,
                user,
                request,
                ai,
                embedder,
                settings,
                scope=scope,
                stream=True,
                request_id=getattr(http_request.state, "request_id", None),
            ):
                if event["type"] == "done":
                    final = annotate(event["response"], selected, request)
                    event = {"type": "done", "response": final.model_dump(mode="json")}
                yield sse(event)
        except Exception as exc:
            error = translate(exc, http_request)
            yield sse(
                {
                    "type": "error",
                    "code": error.code,
                    "message": error.message,
                    "status": error.status,
                }
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
