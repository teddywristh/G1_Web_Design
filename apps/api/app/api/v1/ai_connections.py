from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.errors import APIError
from app.dependencies import admin_user, current_user, expected_version, get_repository
from app.schemas.ai_connections import ConnectionOut, ConnectionPut, Provider
from app.services import ai_connections as service
from app.services import opencode_oauth

router = APIRouter(prefix="/api/v1", tags=["AI connections"])


def local_oauth(request):
    settings = get_settings()
    if not settings.opencode_chatgpt_local_enabled:
        raise APIError(503, "opencode_unavailable", "ChatGPT local OAuth is disabled")
    if settings.app_env.lower() != "test" and (
        not request.client or request.client.host not in {"127.0.0.1", "::1"}
    ):
        raise APIError(403, "forbidden", "ChatGPT OAuth is available only locally")
    return settings


@router.get("/ai/chatgpt")
def chatgpt_status(request: Request, user=Depends(current_user)):
    local_oauth(request)
    session = opencode_oauth.get(user["id"])
    return {
        "connected": bool(session and session["connected"]),
        "pending": bool(session and not session["connected"]),
    }


@router.post("/ai/chatgpt/start")
def chatgpt_start(request: Request, user=Depends(current_user)):
    return opencode_oauth.start(user["id"], local_oauth(request))


@router.post("/ai/chatgpt/finish")
def chatgpt_finish(request: Request, user=Depends(current_user)):
    local_oauth(request)
    return opencode_oauth.finish(user["id"])


@router.delete("/ai/chatgpt")
def chatgpt_disconnect(request: Request, user=Depends(current_user)):
    local_oauth(request)
    opencode_oauth.disconnect(user["id"])
    return {"connected": False}


@router.get("/ai/connections")
def list_connections(user=Depends(current_user), repo=Depends(get_repository)):
    return service.options(repo, user, get_settings())


@router.put("/ai/connections/{provider}", response_model=ConnectionOut)
def save_personal(
    provider: Provider,
    body: ConnectionPut,
    request: Request,
    user=Depends(current_user),
    repo=Depends(get_repository),
):
    return service.save(repo, user, provider, body, get_settings(), request.state.request_id)


@router.delete("/ai/connections/{provider}", response_model=ConnectionOut)
def delete_personal(
    provider: Provider,
    request: Request,
    version=Depends(expected_version),
    user=Depends(current_user),
    repo=Depends(get_repository),
):
    return service.remove(repo, user, provider, version, get_settings(), request.state.request_id)


@router.put("/admin/ai/connections/{provider}", response_model=ConnectionOut)
def save_shared(
    provider: Provider,
    body: ConnectionPut,
    request: Request,
    user=Depends(admin_user),
    repo=Depends(get_repository),
):
    return service.save(
        repo, user, provider, body, get_settings(), request.state.request_id, shared=True
    )


@router.delete("/admin/ai/connections/{provider}", response_model=ConnectionOut)
def delete_shared(
    provider: Provider,
    request: Request,
    version=Depends(expected_version),
    user=Depends(admin_user),
    repo=Depends(get_repository),
):
    return service.remove(
        repo, user, provider, version, get_settings(), request.state.request_id, shared=True
    )
