import json
import logging
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Query, Response
from requests import RequestException

from src.constants.api_constant import FieldDescription
from src.constants.app_constants import MIME_TYPE
from src.services.confluence_service.services.confluence_service import ConfluenceService
from src.services.cronjob.controllers.document_rag_controller import sync_rag_source
from src.services.manage_rag_sources.models.schema import RagConfluenceManagePostSchema
from src.services.manage_rag_sources.services.manage_source import ManageSource
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import SourceType

# Create router with common tag
router = APIRouter(prefix="/rag-pages", tags=["Manage RAG Pages"])
_logger = logging.getLogger(__name__)


@router.post("/confluence", status_code=201, description="Add confluence page to a RAG source")
async def add_confluence_page(data: RagConfluenceManagePostSchema) -> Response:
    """Add confluence page to a RAG source."""
    response = {"status": "failed", "data": None, "error": None}
    try:
        confluence = ConfluenceService()
        pages_child_id = [page["id"] for page in await confluence.get_all_child_pages(data.page_id) if "id" in page]
        new_page_info = await confluence.add_confluence_page(
            page_id=data.page_id,
            collection_id=int(data.collection_id),
            enable_child_pages=True,
            pages_child_id=pages_child_id,
            called_from_gui=False,
        )
        response["data"] = new_page_info
        response["status"] = "success"
        status_code = 201 if response["data"] else 400
    except ValueError as e:
        response["error"] = str(e)
        status_code = 400
    except RequestException as e:
        response["error"] = (
            "Failed to get page metadata. Please check the "
            f"page ID `{data.page_id}` and try again. This is the error message: {e}"
        )
        status_code = 400

    return Response(content=json.dumps(response), media_type=MIME_TYPE, status_code=status_code)

@router.get("/", description="Get all pages tracking information")
async def get_pages(
    collection_id: str = Query(..., description=FieldDescription.COLLECTION_ID),
    source_type: Optional[SourceType] = Query(None, description="Source type of the pages to get"),
) -> Response:
    """Get all pages tracking information."""
    response = {"status": "failed", "data": None, "error": None}
    try:
        dict_result = ManageSource.fetch_confluence_pages_metadata(collection_id, source_type)
        response["data"] = dict_result
        response["status"] = "success"
        response["notes"] = (
            "This data is in rag sync database which is used for tracking page changes for cronjob. It's "
            "not the data in vector database."
        )
        status_code = 200 if response["data"] else 400
    except ValueError as e:
        response["error"] = str(e)
        status_code = 400

    return Response(content=json.dumps(response), media_type=MIME_TYPE, status_code=status_code)


@router.delete("/", status_code=204, description="Delete pages for a source")
async def delete_pages(
    collection_id: str = Query(..., description="ID of the RAG source collection"),
    source_type: SourceType = Query(..., description="Source type of the pages to delete"),
    page_ids: List[str] = Query(..., description="List of page IDs to delete"),
) -> Response:
    """Delete pages for a source."""
    response = {"status": "failed", "data": Union[Dict, None], "error": None}
    try:
        not_found_page_ids = await ManageSource.delete_pages_for_source(collection_id, source_type, page_ids)
        total_request = len(page_ids)
        if len(not_found_page_ids) == total_request:
            raise RuntimeError("Not all pages were deleted")
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

    return Response(content=json.dumps(response), media_type=MIME_TYPE, status_code=status_code)
