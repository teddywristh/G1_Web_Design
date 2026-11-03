from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.v1.uploads import receive_pdf, send_pdf
from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import verify_firebase_token
from app.dependencies import (
    admin_user,
    current_user,
    expected_version,
    get_bucket,
    get_repository,
)
from app.ingestion import pipeline
from app.schemas import (
    AuditPage,
    DocumentCreate,
    DocumentOut,
    DocumentPage,
    DocumentPatch,
    DocumentQuery,
    ProfilePatch,
    UserOut,
    UserPage,
    UserPatch,
)
from app.services import documents, knowledge, users

router = APIRouter(prefix="/api/v1")


def tagged(response, data):
    response.headers["ETag"] = f'"{data["version"]}"'
    return data


@router.post("/users/me/bootstrap", response_model=UserOut, tags=["users"])
def bootstrap(
    request: Request,
    response: Response,
    token=Depends(verify_firebase_token),
    repo=Depends(get_repository),
):
    return tagged(response, users.bootstrap(repo, token, request.state.request_id))


@router.get("/users/me", response_model=UserOut, tags=["users"])
def me(response: Response, user=Depends(current_user)):
    return tagged(response, user)


@router.patch("/users/me", response_model=UserOut, tags=["users"])
def update_me(
    body: ProfilePatch,
    request: Request,
    response: Response,
    user=Depends(current_user),
    version=Depends(expected_version),
    repo=Depends(get_repository),
):
    return tagged(
        response,
        users.update_user(
            repo, user["id"], body.model_dump(), user["id"], request.state.request_id, version
        ),
    )


@router.get("/documents", response_model=DocumentPage, tags=["documents"])
def document_list(
    params: DocumentQuery = Query(), user=Depends(current_user), repo=Depends(get_repository)
):
    return documents.list_documents(repo, params)


@router.get("/documents/{doc_id}", response_model=DocumentOut, tags=["documents"])
def document_get(
    doc_id: str, response: Response, user=Depends(current_user), repo=Depends(get_repository)
):
    return tagged(
        response, documents.ensure_document(repo.get("legal_documents", doc_id), public=True)
    )


@router.get("/documents/{doc_id}/download", tags=["documents"])
def download(
    doc_id: str,
    user=Depends(current_user),
    repo=Depends(get_repository),
    bucket=Depends(get_bucket),
):
    document = documents.ensure_document(repo.get("legal_documents", doc_id), public=True)
    return send_pdf(bucket, document["storagePath"], f"{doc_id}.pdf")


@router.get("/admin/documents", response_model=DocumentPage, tags=["admin"])
def admin_document_list(
    params: DocumentQuery = Query(), user=Depends(admin_user), repo=Depends(get_repository)
):
    return documents.list_documents(repo, params, admin=True)


@router.get("/admin/documents/{doc_id}", response_model=DocumentOut, tags=["admin"])
def admin_document_get(
    doc_id: str, response: Response, user=Depends(admin_user), repo=Depends(get_repository)
):
    data = repo.get("legal_documents", doc_id)
    if not data:
        raise APIError(404, "not_found", "Document not found")
    return tagged(response, data)


@router.post("/admin/documents", response_model=DocumentOut, status_code=201, tags=["admin"])
def document_create(
    body: DocumentCreate,
    request: Request,
    response: Response,
    user=Depends(admin_user),
    repo=Depends(get_repository),
):
    result = documents.create_document(
        repo, body.model_dump(mode="json"), user["id"], request.state.request_id
    )
    response.headers["Location"] = f"/api/v1/admin/documents/{result['id']}"
    return tagged(response, result)


@router.patch("/admin/documents/{doc_id}", response_model=DocumentOut, tags=["admin"])
def document_patch(
    doc_id: str,
    body: DocumentPatch,
    request: Request,
    response: Response,
    user=Depends(admin_user),
    repo=Depends(get_repository),
    version=Depends(expected_version),
):
    return tagged(
        response,
        documents.patch_document(
            repo,
            doc_id,
            body.model_dump(mode="json", exclude_unset=True),
            user["id"],
            request.state.request_id,
            version,
        ),
    )


@router.put(
    "/admin/documents/{doc_id}/file",
    response_model=DocumentOut,
    tags=["admin"],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def document_upload(
    doc_id: str,
    request: Request,
    response: Response,
    public_embedding_input_confirmed: bool = False,
    user=Depends(admin_user),
    repo=Depends(get_repository),
    bucket=Depends(get_bucket),
    version=Depends(expected_version),
):
    knowledge.ensure_shared_kb(repo, request.state.request_id)
    outbox = pipeline.job_outbox(
        knowledge.SHARED,
        "legal_documents",
        doc_id,
        user["id"],
        "auto",
        get_settings(),
        public_embedding_input_confirmed,
    )
    result = await receive_pdf(
        request,
        documents.upload_document,
        repo,
        bucket,
        doc_id,
        user["id"],
        version,
        outbox=outbox,
    )
    return tagged(response, result)


@router.delete("/admin/documents/{doc_id}", response_model=DocumentOut, tags=["admin"])
def document_delete(
    doc_id: str,
    request: Request,
    response: Response,
    user=Depends(admin_user),
    repo=Depends(get_repository),
    bucket=Depends(get_bucket),
    version=Depends(expected_version),
):
    return tagged(
        response,
        documents.delete_document(
            repo, bucket, doc_id, user["id"], request.state.request_id, version
        ),
    )


@router.get("/admin/users", response_model=UserPage, tags=["admin"])
def user_list(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=3000),
    isActive: bool | None = None,
    user=Depends(admin_user),
    repo=Depends(get_repository),
):
    filters = [("isActive", "==", isActive)] if isActive is not None else []
    return repo.page("users", filters=filters, limit=limit, cursor=cursor)


@router.patch("/admin/users/{uid}", response_model=UserOut, tags=["admin"])
def user_update(
    uid: str,
    body: UserPatch,
    request: Request,
    response: Response,
    user=Depends(admin_user),
    repo=Depends(get_repository),
    version=Depends(expected_version),
):
    return tagged(
        response,
        users.update_user(
            repo, uid, body.model_dump(), user["id"], request.state.request_id, version
        ),
    )


@router.get("/admin/audit-logs", response_model=AuditPage, tags=["admin"])
def audit_list(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=3000),
    event: str | None = Query(None, min_length=1, max_length=100),
    user=Depends(admin_user),
    repo=Depends(get_repository),
):
    filters = [("event", "==", event)] if event else []
    return repo.page("system_logs", filters=filters, limit=limit, cursor=cursor)
