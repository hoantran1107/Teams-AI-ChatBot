from fastapi import APIRouter, Response, Query, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.services.rag_services.services.kb_rag_service import KBRagService
from src.services.postgres.db_utils import get_db


# Define Pydantic model for request/response schema
class GetRagModel(BaseModel):
    question: str
    is_use_history: bool = False
    analyze_mode: bool = False


# Create FastAPI router
router = APIRouter(prefix="/rag", tags=["RAG Company"])


@router.get("/kb", description="Answer question based on KB documents")
async def get_kb_rag_answer(
    question: str = Query(..., description="The question to be answered"),
    is_use_history: bool = Query(
        False, description="Whether to use conversation history"
    ),
    db: Session = Depends(get_db),
):
    """
    Answer questions based on KB documents
    """
    if is_use_history:
        response: str = await KBRagService.ask_with_memory(question)
    else:
        response: str = await KBRagService.ask_with_no_memory(question)

    return Response(content=response, media_type="text/plain")
