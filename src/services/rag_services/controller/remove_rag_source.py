from fastapi import APIRouter, Response, Query
from typing import List, Optional, Union
import json
from src.services.manage_rag_sources.services.manage_source import ManageSource
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import SourceType

router = APIRouter(prefix="/rag", tags=["RAG Company"])

MIME_TYPE = "application/json"


@router.delete(
    "/remove-documents", description="Remove specific documents from a RAG source"
)
async def remove_documents(
    collection_id: str = Query(..., description="ID of the RAG source collection"),
    source_type: SourceType = Query(
        ..., description="Source type of the pages to delete"
    ),
    page_ids: List[str] = Query(..., description="List of page IDs to delete"),
):
    """
    Remove specific documents from a RAG source
    """
    response = {"status": "failed", "data": Union[dict, None], "error": None}
    try:
        not_found_page_ids = ManageSource.delete_pages_for_source(
            collection_id, source_type, page_ids
        )
        total_request = len(page_ids)
        if len(not_found_page_ids) == total_request:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to delete any pages - all {total_request} requested pages were not found"
            )

        response["status"] = "success"
        response["data"] = {
            "message": f"Deleted {total_request - len(not_found_page_ids)}/{total_request} pages successfully",
            "not_found_page_ids": not_found_page_ids,
        }
        status_code = 200 if response["status"] == "success" else 400
    except Exception as e:
        response["error"] = str(e)
        response["data"] = None
        status_code = 400

    return Response(
        content=json.dumps(response), media_type=MIME_TYPE, status_code=status_code
    )
