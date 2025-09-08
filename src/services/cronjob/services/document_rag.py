import json
import logging
import os
import tempfile
import traceback
from dataclasses import asdict, dataclass
from typing import Awaitable, Callable, Optional, Type

from src.common.service_result import ServiceResult
from src.config.database_config import db
from src.config.settings import atlassian_api_token, atlassian_user
from src.enums.enum import ServiceResultEnum
from src.services.confluence_service.services.confluence_service import (
    ConfluenceService,
)
from src.services.cronjob.models.source_handler import (
    BaseSourceHandler,
    DocumentMetadata,
)
from src.services.cronjob.models.source_handler.confluence_source_handler import (
    ConfluenceSourceHandler,
)
from src.services.cronjob.models.source_handler.gcp_handler import GCPSourceHandler
from src.services.cronjob.services.rag_store_services import RagStoreService
from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service

from src.services.postgres.document_rag import DocumentRag
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import (
    Collection,
    DocumentLog,
    SourceType,
    SyncLog,
)
from src.services.rag_services.models.document_retriever import DocumentRetriever

_logger = logging.getLogger("CronjobDocumentRag")


@dataclass
class TypeChangeLog:
    success: list[str]
    failed: list[str]
    error_message: Optional[str] = None


@dataclass
class SyncProcessLog:
    source_type: str
    source_path: str
    updates: list[TypeChangeLog]
    deletes: list[TypeChangeLog]
    news: list[TypeChangeLog]
    error: Optional[str] = None


class CronjobDocumentRag:
    """Class to handle document synchronization and processing for cronjob."""

    _handlers: dict[SourceType, Type[BaseSourceHandler]] = {
        SourceType.GCP: GCPSourceHandler,
        SourceType.CONFLUENCE: ConfluenceSourceHandler,
    }

    def __init__(self, collection: "Collection") -> None:
        """Initialize the CronjobDocumentRag class."""
        self.collection = collection
        self.work_dir = None

        self.gcp_bucket_service = gcp_bucket_service
        self.confluence_service = ConfluenceService(collection_id=collection.id)

        self.document_rag = DocumentRag(collection)
        if collection.user_id is None:
            self.doc_retriever = DocumentRetriever.get_doc_retriever(collection.name)
        else:
            self.doc_retriever = DocumentRetriever.get_doc_retriever(f"{collection.name}_{collection.user_id}")

        self.rag_store_service = RagStoreService(self.doc_retriever)

    async def sync_by_source(self, source_type: SourceType, source_path: str, **config) -> tuple[bool, SyncProcessLog]:
        """Sync documents from a specific source to a specific collection."""
        collection_id = config["collection_id"]
        _logger.info("Starting sync for %s at %s to collection %s", source_type.value, source_path, collection_id)

        try:
            # Get handler for a source type
            handler_class = self._handlers.get(source_type)
            if not handler_class:
                raise ValueError(f"No handler registered for {source_type.value}")

            handler = handler_class(source_path, **config)

            # Get remote documents
            changes_docs = await handler.list_new_updated_delete_docs()

            # Process documents
            success, results_logs = await self._sync_documents(source_type, source_path, changes_docs)
            return success, results_logs

        except Exception as e:
            _logger.error(
                f"Sync failed: {str(e)}. Traceback: {traceback.format_exc()}",
                exc_info=True,
            )
            return False, SyncProcessLog(
                source_type=source_type.value,
                source_path=source_path,
                error=str(e),
                news=[],
                updates=[],
                deletes=[],
            )

    async def _sync_documents(
        self,
        source_type: SourceType,
        source_path: str,
        changes_docs: dict[str, list[DocumentMetadata]],
    ) -> tuple[bool, SyncProcessLog]:
        """Sync documents and return statistics."""
        results = {}
        success = False

        # Define a mapping of change types to their corresponding methods
        type_handlers: dict[str, Callable[[list[DocumentMetadata]], Awaitable[TypeChangeLog]]] = {
            "news": self.vectorstore_add_files,
            "updates": self.vectorstore_update_files,
            "deletes": self.vectorstore_delete_files,
        }

        # Process each change type
        for type_change, docs in changes_docs.items():
            if handler := type_handlers.get(type_change):
                results[type_change] = await handler(docs)
                if results[type_change].success:
                    success = True

        if not success:
            # if not failed and not success, that means we dont update anything -> success=True
            count = 0
            for result in results.values():
                count += (not result.failed) + (not result.success)
            # if count == 6, that means we dont update anything -> success=True
            # not result.failed = true -> means we have no failed docs
            # not result.success = true -> means we have no success docs
            if count == 6:
                success = True

        return success, SyncProcessLog(
            news=results.get("news", []),
            updates=results.get("updates", []),
            deletes=results.get("deletes", []),
            source_type=source_type.value,
            source_path=source_path,
        )

    async def sync_by_collection(self):
        """Sync all sources that have documents in a collection."""
        _logger.info("Starting sync for collection %s", self.collection.name)

        # Find all unique sources in a collection
        sources = (
            db.session.query(DocumentLog.source_type, DocumentLog.source_path)
            .filter_by(collection_id=self.collection.id)
            .distinct()
            .all()
        )

        if not sources:
            return True, []

        sync_logs = []
        at_least_one_success = False
        all_log_messages = []
        for source_type, source_path in sources:
            # Get config for this source
            config = self._get_source_config(source_type)
            is_success, result_log = await self.sync_by_source(source_type, source_path, **config)
            result_log_dict = asdict(result_log)
            all_log_messages.append(result_log_dict)
            if not is_success:
                _logger.error(
                    "Failed to sync %s at %s to collection %s", source_type.value, source_path, self.collection.id
                )
                continue
            sync_logs.append(
                SyncLog(
                    source_type=source_type,
                    source_path=source_path,
                    collection_id=self.collection.id,
                    documents_added=0,
                    documents_updated=0,
                    documents_deleted=0,
                    notes=json.dumps(result_log_dict),
                )
            )
            at_least_one_success = True

        db.session.bulk_save_objects(sync_logs)
        db.session.commit()

        return at_least_one_success, all_log_messages

    def _get_source_config(self, source_type: SourceType) -> dict:
        """Get configuration for a source."""
        default_config = {
            "collection_id": self.collection.id,
            "work_dir": self.work_dir,
        }
        if source_type == SourceType.CONFLUENCE:
            return {
                "username": atlassian_user,
                "password": atlassian_api_token,
                **default_config,
            }
        return default_config

    async def vectorstore_add_files(self, new_files: list[DocumentMetadata]) -> TypeChangeLog:
        """Process new files and add them to the vector store."""
        successful = []
        failed_files = []
        error_message = None
        for file_ in new_files:
            try:
                (
                    success,
                    error_message,
                ) = await self.rag_store_service.add_documents_to_vector_store(
                    file_name=file_.download_url or "",
                    topic_name=file_.display_name,
                    view_url=file_.source_metadata.get("public_url") or "",
                )
                if success:
                    db_document_log = file_.db_instance
                    db_document_log.previous_version = db_document_log.version
                    db_document_log.is_new_doc = False
                    db_document_log.content_hash = file_.content_hash
                    db_document_log.version = file_.version
                    db_document_log.source_updated_date = file_.source_metadata.get("updated_date")
                    successful.append(file_.display_name)
                    db.session.commit()
                else:
                    _logger.error(
                        f"Failed to add {file_.display_name} to vector store in {self.collection.name} collection id {self.collection.id}: {error_message}"
                    )
            except Exception as e:
                _logger.error(f"Failed to process new file {file_}: {str(e)}", exc_info=True)
                failed_files.append(file_.display_name)
                db.session.rollback()

        return TypeChangeLog(success=successful, failed=failed_files, error_message=error_message)

    async def vectorstore_update_files(self, updated_files: list[DocumentMetadata]):
        """Process updated files and update them in the vector store."""
        successful = []
        failed = []
        for file_ in updated_files:
            try:
                doc_id_prefix = os.path.splitext(os.path.basename(file_.download_url))[0]
                success = await self.rag_store_service.update_rag_vector_store(
                    doc_id_prefix,
                    file_.download_url,
                    file_.source_metadata.get("source_path"),
                    already_downloaded=True,
                    topic_name=file_.display_name,
                )
                if success:
                    db_document_log = file_.db_instance
                    db_document_log.previous_version = db_document_log.version
                    db_document_log.is_new_doc = False
                    db_document_log.version = file_.version
                    db_document_log.content_hash = file_.content_hash
                    if source_updated_date := file_.source_metadata.get("updated_date"):
                        db_document_log.source_updated_date = source_updated_date
                    successful.append(file_.display_name)
                    db.session.commit()
                else:
                    raise ValueError(f"Failed to update {file_} in vector store")
            except Exception as e:
                _logger.error(f"Failed to update file {file_}: {str(e)}", exc_info=True)
                failed.append(file_.display_name)
                db.session.rollback()

        return TypeChangeLog(success=successful, failed=failed)

    async def vectorstore_delete_files(self, deleted_files: list[DocumentMetadata]):
        """Process deleted files and remove them from the vector store"""
        successful = []
        failed = []
        for file_ in deleted_files:
            try:
                doc_id_prefix = file_.identity_constant_name
                await self.rag_store_service.delete_document_with_doc_prefix(doc_id_prefix)
                successful.append(file_.display_name)
                db_document_log = file_.db_instance
                db_document_log.delete()
                db.session.commit()
            except Exception as e:
                _logger.error(f"Failed to delete file {file_}: {str(e)}", exc_info=True)
                failed.append(file_.display_name)
                db.session.rollback()
        return TypeChangeLog(success=successful, failed=failed)

    async def process_cronjob_async(self) -> ServiceResult:
        """Process cronjob to sync documents from GCP to PostgreSQL and update vector store."""
        response = ServiceResult()
        with tempfile.TemporaryDirectory() as work_dir:
            try:
                self.work_dir = work_dir
                _logger.info("Work dir: %s", self.work_dir)
                _logger.info("Starting cronjob for %s", self.collection.name)

                # Sync documents from GCP to PostgreSQL: interact with logging tables
                at_least_one_success, all_log_messages = await self.sync_by_collection()
                response.data = all_log_messages
                response.status = ServiceResultEnum.SUCCESS if at_least_one_success else ServiceResultEnum.FAILED
                _logger.info("Cronjob for %s completed", self.collection.name)
            except Exception as e:
                # Log critical errors for debugging
                response.error = str(e)
                _logger.exception("Critical error in cronjob: %s", str(e))
            finally:
                self.work_dir = None

        return response
