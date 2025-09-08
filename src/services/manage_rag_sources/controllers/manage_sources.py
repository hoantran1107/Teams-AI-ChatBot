import json
from typing import Dict, Optional, Union

from fastapi import APIRouter, Query, Response

from src.constants.app_constants import MIME_TYPE
from src.services.manage_rag_sources.services.manage_source import ManageSource

# Create router
router = APIRouter(prefix="/rag-sources", tags=["Manage RAG Sources"])


@router.post("/source", status_code=201, description="Add a RAG source")
async def add_rag_source(
    source_name: str = Query(..., description="Name of the RAG source"),
    note: str = Query(..., description="Description of the RAG source", min_length=10),
    run_cron_job: bool = Query(True, description="Run cron job for the source"),
    user_id: Optional[str] = Query(
        None, description="User ID of the person who triggered the request"
    ),
):
    """
    Add a new RAG source
    """
    response = {"status": "failed", "data": Union[None, Dict], "error": None}
    assert isinstance(run_cron_job, bool), "run_cron_job must be a boolean value."
    try:
        new_collection_info: dict = ManageSource.add_source(
            source_name=source_name,
            user_id=user_id,
            note=note,
            run_cron_job=run_cron_job,
        )
        response["data"] = new_collection_info
        response["status"] = "success"
        status_code = 201 if response["data"] else 400
    except ValueError as e:
        response["error"] = str(e)
        status_code = 400

    return Response(
        content=json.dumps(response), media_type=MIME_TYPE, status_code=status_code
    )


@router.get("/sources", description="Get all RAG sources")
async def get_all_rag_sources():
    """
    Get all RAG sources
    """
    all_sources: dict = ManageSource.get_all_sources()
    return Response(
        content=json.dumps(all_sources), media_type=MIME_TYPE, status_code=200
    )


@router.delete("/source", status_code=204, description="Delete a RAG source")
async def delete_rag_source(
    source_id: int = Query(
        ...,
        description="ID of the RAG source to delete",
    )
):
    try:
        await ManageSource.aremove_source(source_id=source_id)
        return Response(status_code=204)
    except Exception as e:
       return Response(
            content=json.dumps({
                "message": str(e),
            }),
            media_type=MIME_TYPE,
            status_code=400
        )