from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.core.database import get_database
from app.schemas.rag import AskRequest, AskResponse
from app.services.ai import OpenAIService
from app.services.rag import answer_question
from app.services.retrieval import retrieve_chunks

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ask", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    database=Depends(get_database),
) -> AskResponse:
    settings = get_settings()
    ai = OpenAIService(settings)
    try:
        query_embedding = ai.embed([request.question])[0]
        chunks = retrieve_chunks(database, query_embedding, request.question, request.top_k)
        return answer_question(request.question, chunks, ai, settings)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="RAG request failed.") from error
