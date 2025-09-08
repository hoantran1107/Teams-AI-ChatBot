from fastapi import APIRouter, Response, Query, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.services.rag_services.models.exceptions import DataSourceNotExistException
from src.services.rag_services.services.dynamic_rag_service import DynamicRagService
from src.services.postgres.db_utils import get_db


# Define Pydantic model for request schema
class GetRagDynamicModel(BaseModel):
    question: str
    rag_source: str
    analyze_mode: bool = False


# Create FastAPI router
router = APIRouter(prefix="/rag", tags=["RAG Company"])


@router.get("/dynamic", description="Answer question based on specific documents")
async def get_dynamic_rag_answer(
    question: str = Query(..., description="The question to be answered"),
    rag_source: str = Query(..., description="The RAG source to use"),
    analyze_mode: bool = Query(False, description="Whether to use analysis mode"),
    db: Session = Depends(get_db),
):
    """
    Answer questions based on specific documents
    """
    try:
        service = DynamicRagService(rag_source)
        response = await service.ask_with_no_memory(
            question, db=db, analyze_mode=analyze_mode
        )
        return Response(content=response, media_type="text/plain")
    except DataSourceNotExistException as e:
        return Response(content=str(e), media_type="text/plain", status_code=404)
