from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.dependencies import admin_user, current_user, expected_version, get_repository
from app.schemas.ai_connections import ConnectionOut, ConnectionPut, Provider
from app.services import ai_connections as service

router = APIRouter(prefix="/api/v1", tags=["AI connections"])


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
