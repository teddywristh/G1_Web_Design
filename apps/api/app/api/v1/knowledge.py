from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.v1.uploads import receive_pdf
from app.core.config import get_settings
from app.core.errors import APIError
from app.dependencies import (
    admin_user,
    current_user,
    expected_version,
    get_bucket,
    get_repository,
)
from app.schemas.knowledge import (
    EvidenceOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeDocumentCreate,
    KnowledgeDocumentOut,
    KnowledgeDocumentPage,
    ProcessingOut,
    ProvisionReview,
    PublishRequest,
)
from app.services import documents, evidence, knowledge

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


def tagged(response, data):
    response.headers["ETag"] = f'"{data["version"]}"'
    return data


def uploads_enabled():
    if not get_settings().knowledge_upload_enabled:
        raise APIError(503, "feature_disabled", "Knowledge upload is disabled")


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseOut])
def kb_list(user=Depends(current_user), repo=Depends(get_repository)):
    return knowledge.list_kbs(repo, user, get_settings())


@router.post("/knowledge-bases", response_model=KnowledgeBaseOut, status_code=201)
def kb_create(
    body: KnowledgeBaseCreate,
    request: Request,
    response: Response,
    user=Depends(current_user),
    repo=Depends(get_repository),
):
    uploads_enabled()
    result = knowledge.create_kb(repo, user, body.title, request.state.request_id, get_settings())
    return tagged(response, result)


@router.get("/knowledge-bases/{kb_id}/documents", response_model=KnowledgeDocumentPage)
def document_list(
    kb_id: str,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=3000),
    user=Depends(current_user),
    repo=Depends(get_repository),
):
    return knowledge.list_documents(repo, user, kb_id, limit, cursor)


@router.post(
    "/knowledge-bases/{kb_id}/documents", response_model=KnowledgeDocumentOut, status_code=201
)
def document_create(
    kb_id: str,
    body: KnowledgeDocumentCreate,
    request: Request,
    response: Response,
    user=Depends(current_user),
    repo=Depends(get_repository),
):
    uploads_enabled()
    result = knowledge.create_document(
        repo, user, kb_id, body.model_dump(mode="json"), request.state.request_id
    )
    return tagged(response, result)


@router.put(
    "/knowledge-bases/{kb_id}/documents/{doc_id}/file",
    response_model=KnowledgeDocumentOut,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def document_upload(
    kb_id: str,
    doc_id: str,
    request: Request,
    response: Response,
    credential_source: Literal["auto", "personal", "shared"] = "auto",
    user=Depends(current_user),
    repo=Depends(get_repository),
    bucket=Depends(get_bucket),
    version=Depends(expected_version),
):
    uploads_enabled()
    knowledge.private_document(repo, user, kb_id, doc_id)
    options = knowledge.upload_options(user, kb_id, doc_id, credential_source, get_settings())
    result = await receive_pdf(
        request, documents.upload_document, repo, bucket, doc_id, user["id"], version, **options
    )
    return tagged(response, result)


@router.get("/knowledge-bases/{kb_id}/documents/{doc_id}/processing", response_model=ProcessingOut)
def document_processing(
    kb_id: str, doc_id: str, user=Depends(current_user), repo=Depends(get_repository)
):
    document = knowledge.private_document(repo, user, kb_id, doc_id)
    return knowledge.processing(repo, document, get_settings())


@router.post("/knowledge-bases/{kb_id}/documents/{doc_id}/reprocess", response_model=ProcessingOut)
def document_reprocess(
    kb_id: str,
    doc_id: str,
    request: Request,
    user=Depends(current_user),
    repo=Depends(get_repository),
    version=Depends(expected_version),
):
    uploads_enabled()
    document = knowledge.private_document(repo, user, kb_id, doc_id)
    return knowledge.reprocess(
        repo, document, user, version, request.state.request_id, get_settings()
    )


@router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}", response_model=KnowledgeDocumentOut)
def document_delete(
    kb_id: str,
    doc_id: str,
    request: Request,
    response: Response,
    user=Depends(current_user),
    repo=Depends(get_repository),
    bucket=Depends(get_bucket),
    version=Depends(expected_version),
):
    result = knowledge.delete_document(
        repo, bucket, user, kb_id, doc_id, request.state.request_id, version
    )
    return tagged(response, result)


@router.get("/evidence/{evidence_id}", response_model=EvidenceOut)
def evidence_get(evidence_id: str, user=Depends(current_user), repo=Depends(get_repository)):
    return evidence.read(repo, user, evidence_id)


@router.post("/admin/knowledge-bases/{kb_id}/publish", response_model=KnowledgeBaseOut)
def kb_publish(
    kb_id: str,
    body: PublishRequest,
    request: Request,
    response: Response,
    user=Depends(admin_user),
    repo=Depends(get_repository),
    version=Depends(expected_version),
):
    result = knowledge.publish_generation(
        repo,
        kb_id,
        body.generationId,
        version,
        user["id"],
        request.state.request_id,
        get_settings(),
    )
    return tagged(response, result)


@router.patch("/admin/provisions/{provision_id}")
def provision_review(
    provision_id: str,
    body: ProvisionReview,
    request: Request,
    user=Depends(admin_user),
    repo=Depends(get_repository),
    version=Depends(expected_version),
):
    data = body.model_dump(mode="json", exclude_unset=True)
    result = knowledge.review_provision(
        repo, provision_id, data, user["id"], request.state.request_id, version
    )
    return {"id": result["id"], "version": result["version"]}
