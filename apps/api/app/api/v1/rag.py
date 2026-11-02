from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.errors import APIError
from app.dependencies import current_user, get_repository
from app.schemas.rag import AskRequest, AskResponse
from app.services import qa
from app.services.ai import AnthropicService, OpenAIService
from app.services.ai_connections import Credential, resolve
from app.services.opencode import OpenCodeService
from app.services.opencode_oauth import OAuthAnswer

router = APIRouter(prefix="/rag", tags=["rag"])


def openai_settings(settings, credential, model=None):
    return settings.model_copy(
        update={
            "openai_api_key": credential.api_key,
            "default_llm_model": model or settings.default_llm_model,
        }
    )


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
    if request.engine == "opencode":
        if not settings.opencode_local_enabled:
            raise APIError(503, "opencode_unavailable", "OpenCode local worker is not enabled")
        if settings.app_env.lower() != "test" and (
            not http_request.client or http_request.client.host not in {"127.0.0.1", "::1"}
        ):
            raise APIError(403, "forbidden", "OpenCode worker is available only locally")
        if request.provider not in {"openai", "deepseek", "openrouter"}:
            raise APIError(422, "invalid_provider", "This provider is not enabled for OpenCode")
        if request.provider != "openai" and not request.model:
            raise APIError(422, "invalid_model", "Select a model for this provider")
    elif request.provider not in {"openai", "anthropic"}:
        raise APIError(422, "invalid_provider", "This provider requires OpenCode")
    if request.credential_source == "chatgpt":
        if (
            request.engine != "opencode"
            or request.provider != "openai"
            or not settings.opencode_chatgpt_local_enabled
        ):
            raise APIError(422, "invalid_provider", "ChatGPT sign-in requires local OpenCode")
        if request.retrieval_mode != "keyword":
            raise APIError(422, "invalid_retrieval", "ChatGPT sign-in requires keyword retrieval")
        selected = Credential("openai", "", "chatgpt")
        ai = OAuthAnswer(user["id"], request.model)
    elif request.engine == "opencode":
        selected = resolve(repo, user, request.provider, request.credential_source, settings)
        ai = OpenCodeService(settings, selected.api_key, request.model, provider=request.provider)
    elif request.provider == "openai":
        selected = resolve(repo, user, request.provider, request.credential_source, settings)
        ai = OpenAIService(openai_settings(settings, selected, request.model))
    else:
        selected = resolve(repo, user, request.provider, request.credential_source, settings)
        ai = AnthropicService(settings, selected.api_key, request.model)
    try:
        embedder = None
        if request.retrieval_mode == "hybrid":
            if request.provider == "openai" and request.engine == "direct":
                embedder = ai
            else:
                # Never silently borrow a shared embedding key when personal-only was selected.
                embedding_key = resolve(repo, user, "openai", request.credential_source, settings)
                embedder = OpenAIService(openai_settings(settings, embedding_key))
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
