from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.database import get_database
from app.core.errors import APIError
from app.dependencies import current_user, get_repository
from app.schemas.rag import AskRequest, AskResponse
from app.services.ai import AnthropicService, OpenAIService
from app.services.ai_connections import resolve
from app.services.rag import answer_question
from app.services.retrieval import retrieve_chunks

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
    database=Depends(get_database),
    user=Depends(current_user),
    repo=Depends(get_repository),
) -> AskResponse:
    settings = get_settings()
    selected = resolve(repo, user, request.provider, request.credential_source, settings)
    if request.provider == "openai":
        ai = OpenAIService(openai_settings(settings, selected, request.model))
    else:
        ai = AnthropicService(settings, selected.api_key, request.model)
    try:
        query_embedding = None
        if request.retrieval_mode == "hybrid":
            if request.provider == "openai":
                embedder = ai
            else:
                # Never silently borrow a shared embedding key when personal-only was selected.
                embedding_key = resolve(repo, user, "openai", request.credential_source, settings)
                embedder = OpenAIService(openai_settings(settings, embedding_key))
            query_embedding = embedder.embed([request.question])[0]
        chunks = retrieve_chunks(database, query_embedding, request.question, request.top_k)
        result = answer_question(request.question, chunks, ai, settings)
        return result.model_copy(
            update={"provider": selected.provider, "credential_source": selected.source}
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
