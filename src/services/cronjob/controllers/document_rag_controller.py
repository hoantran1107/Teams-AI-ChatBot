import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query, Response

from src.constants.app_constants import MIME_TYPE
from src.enums.enum import ServiceResultEnum
from src.services.cronjob.services.document_rag import CronjobDocumentRag
from src.services.manage_rag_sources.services.manage_source import ManageSource
from src.services.postgres.models.tables.rag_sync_db.cronjob_log import CronJobLog
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import Collection

# Create router
router = APIRouter(prefix="/cronjob", tags=["Cronjob Services"])


@router.put(
    "/sync-source",
    description="Upsert document to PostgreSQL database for a specific RAG source",
)
async def sync_rag_source(
    collection_id: Annotated[str, Query(..., min_length=1, description="The id of the source")],
) -> Response:
    """Upsert document to PostgreSQL database for a specific RAG source."""

    response = await ManageSource.sync_rag_source(collection_id)
    return Response(
            content=json.dumps(response.to_dict()),
            status_code= 200 if response.status == ServiceResultEnum.SUCCESS else 400,
            media_type=MIME_TYPE,
        )

@router.get(
    "/sync-all-sources",
    description="Upsert document to PostgreSQL database for all RAG sources",
)
async def sync_all_rag_sources() -> Response:
    """Upsert document to PostgreSQL database for all RAG sources."""
    latest_log = CronJobLog.get_latest_log()

    cronjob_log = {}
    need_wait = False
    if not latest_log or not latest_log.is_processing:
        collections = Collection.get_cron_job_collections()
        if not collections:
            return Response(
                content=json.dumps({"status": "failed", "message": "No collections found"}),
                status_code=400,
                media_type=MIME_TYPE,
            )

        log_id = CronJobLog.create_new_log(collections, is_processing=True)
        is_success = True
        log_message = None

        try:
            for collection in collections:
                cronjob_service = CronjobDocumentRag(collection)
                response = await cronjob_service.process_cronjob_async()
                cronjob_log[collection.name] = response
            log_message = json.dumps(cronjob_log, indent=4)
        except Exception as e:
            is_success = False
            log_message = str(e)
        finally:
            CronJobLog.update_log(
                log_id,
                is_processing=False,
                is_success=is_success,
                log=log_message,
                end_time=datetime.now(tz=timezone.utc),
            )
    else:
        need_wait = True
        cronjob_log["message"] = "The previous cronjob is still processing. Please try again later."

    status_code = 200 if not need_wait else 409
    return Response(content=json.dumps(cronjob_log), status_code=status_code, media_type=MIME_TYPE)
