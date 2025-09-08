from fastapi import APIRouter, Response, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.services.rag_services.services.multiple_rag_sources import MultiRagService
from src.services.postgres.db_utils import get_db

# Define Pydantic model for request schema
class RagSource(BaseModel):
    source_name: str = Field(..., description="The name of the RAG source")

class GetMultiRagModel(BaseModel):
    question: str = Field(..., description="The question to be answered")
    rag_sources: List[RagSource] = Field(..., description="List of RAG sources which can be used to answer the question")
    session_id: Optional[str] = Field(None, description="Optional session identifier to maintain context across multiple requests")
    analyze_mode: Optional[bool] = Field(False, description="Whether to analyze tables in the response")

# Create FastAPI router
router = APIRouter(prefix="/rag", tags=["RAG Company"])

# Removing the GET endpoint as it's not suitable for complex parameters like lists of dictionaries
# Instead, use only the POST endpoint for API calls which can properly handle the JSON body

@router.post("/multi-classic", 
            description="Answer question based on multiple RAG sources (JSON body)")
async def post_multi_rag_answer(
    request: GetMultiRagModel,
    db: Session = Depends(get_db)
):
    """
    Get answers based on multiple RAG sources using a JSON request body
    
    Each RAG source should have the format: {"source_name": "Source Name"}
    """
    try:
        # Convert list of RagSource objects to list of dicts with source_name key
        rag_sources = [{"source_name": source.source_name} for source in request.rag_sources]
        
        response = await MultiRagService.ask_with_no_memory_multi(
            question=request.question, 
            rag_sources=rag_sources,
            db=db, 
            analyze_mode=request.analyze_mode
        )
        return Response(content=response, media_type='text/plain')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
