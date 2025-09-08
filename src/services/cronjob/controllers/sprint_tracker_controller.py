import json
from typing import Optional

from fastapi import APIRouter, Query, Response

from src.constants.app_constants import MIME_TYPE
from src.services.cronjob.services.generate_sprint import generate_sprint

router = APIRouter()


@router.get("/cronjob/sprint-tracker", tags=["Cronjob Services"], description="Trigger cronjob for Sprint Tracker")
async def process_sprint_tracker(
    board_id: Optional[int] = Query(427, description="The ID of the board to process"),
    project_key: Optional[str] = Query("IFDCPB", description="The project key to process"),
    bypass: Optional[bool] = Query(False, description="Bypass the sprint end date check for cronjob"),
):
    """Process cronjob for Sprint Tracker."""
    try:
        await generate_sprint(board_id, project_key, bypass)
        return Response(
            content=json.dumps({"message": "Sprint Tracker cronjob processed successfully"}),
            media_type=MIME_TYPE,
            status_code=200,
        )
    except ValueError as e:
        return Response(content=json.dumps({"error": str(e)}), media_type=MIME_TYPE, status_code=404)
