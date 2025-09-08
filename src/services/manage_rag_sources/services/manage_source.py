import logging
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from src.common.service_result import ServiceResult
from src.config.database_config import db
from src.config.database_config import db as db_interface

# Updated imports to use the new structure
from src.enums.enum import ServiceResultEnum
from src.services.cronjob.models.source_handler.gcp_handler import (
    file_bucket_hash_name,
    get_metadata_with_validation,
    parse_gcs_url,
)
from src.services.cronjob.services.document_rag import CronjobDocumentRag
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import (
    Collection,
    DocumentLog,
    SourceType,
    SyncLog,
)
from src.services.postgres.models.tables.vector_db import (
    MyCollectionStore,
    MyEmbeddingStore,
)
from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.utils.gcp_helper import GCPHelper

logger = logging.getLogger(__name__)


class ManageSource:
    @classmethod
    async def add_gcp_page(cls, file_links, public_view_urls, collection_id):
        collection = Collection.find_by_filter(id=collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} does not exist, please refresh the page and try again")

        public_view_url_map = {
            file_link: public_view_url for file_link, public_view_url in zip(file_links, public_view_urls)
        }
        # filter out already files
        file_links = list(set(file_links))
        file_links_map = {file_bucket_hash_name(parse_gcs_url(url)[3]): url for url in file_links}
        file_links, not_found_file_links = DocumentLog.get_existing_pages(
            collection_id, SourceType.GCP, list(file_links_map.keys())
        )
        file_links = [file_links_map[identity_constant_name] for identity_constant_name in file_links]
        not_found_file_links = [
            file_links_map[identity_constant_name] for identity_constant_name in not_found_file_links
        ]
        if not_found_file_links:
            try:
                document_log_instances = []
                for file_link in not_found_file_links:
                    file_metadata = await get_metadata_with_validation(file_link)
                    document_log_instances.append(
                        DocumentLog(
                            identity_constant_name=file_metadata.name,
                            display_name=file_metadata.file,
                            version=str(file_metadata.version),
                            created_date=file_metadata.created,
                            updated_date=file_metadata.updated,
                            source_created_date=file_metadata.created,
                            source_updated_date=file_metadata.updated,
                            content_hash=file_metadata.md5_hash,
                            collection_id=collection_id,
                            source_type=SourceType.GCP,
                            source_path=file_metadata.bucket_folder_path,
                            is_new_doc=True,
                            url_download=file_link,
                            data_source_metadata=dict(
                                user_id=file_metadata.user_id,
                                collection=file_metadata.collection,
                                content_type=file_metadata.content_type,
                                metageneration=file_metadata.metageneration,
                                etag=file_metadata.etag,
                                public_url=public_view_url_map[file_link],
                            ),
                        )
                    )
                db.session.add_all(document_log_instances)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                raise e

        return file_links, not_found_file_links

    @classmethod
    def add_source(
        cls,
        source_name: str,
        db: Session = None,
        user_id: str = None,
        note: str = None,
        run_cron_job=True,
    ):
        db_to_use = db if db is not None else db_interface.session

        collection = Collection.find_by_filter(name=source_name, db_session=db_to_use, user_id=user_id)
        if collection:
            raise ValueError(f"Collection {source_name} already exists")
        new_instance = Collection.create(
            name=source_name,
            db_session=db_to_use,
            run_cron_job=run_cron_job,
            user_id=user_id,
            note=note,
        )

        return new_instance.to_dict()

    @classmethod
    def get_all_sources(cls, db: Session = None):
        db_to_use = db if db is not None else db_interface.session
        return list(map(lambda row: row.to_dict(), Collection.find_all(db_session=db_to_use)))

    @classmethod
    async def aremove_source(cls, source_id, db: Session | None = None):
        # Ensure source_id is int if possible
        if source_id is not None and isinstance(source_id, str) and source_id.isdigit():
            source_id = int(source_id)
        """Remove a RAG source and all its documents.
        Args:
            source_id_or_name (str): ID or name of the source to remove
            db (Session, optional): Database session. Defaults to None.
        Raises:
            ValueError: If the source is a default source or doesn't exist
            ValueError: If the source cannot be removed (e.g. default source)
        """
        if source_id is None:
            raise ValueError("Source ID or name must be provided for removal.")
        db_to_use = db if db is not None else db_interface.session

        collection = Collection.find_by_filter(
            id=int(source_id),
            db_session=db_to_use,
        )
        if not collection:
            raise ValueError(f"Source with ID {source_id} not found.")
        collection = collection[0]
        collection_name = str(
            f"{collection.name}_{collection.user_id}" if collection.user_id is not None else collection.name,
        )

        # Refactored: Delete all GCP files for this collection
        cls._delete_gcp_files_for_collection(collection.id, db_to_use)

        DocumentLog.delete_by_filter(db_session=db_to_use, collection_id=collection.id)
        SyncLog.delete_by_filter(db_session=db_to_use, collection_id=collection.id)

        doc_retriever = DocumentRetriever.create_doc_retriever(
            collection_name=collection_name,
        )
        await doc_retriever.adelete_collection()
        Collection.delete_by_filter(id=collection.id, db_session=db_to_use)

    @classmethod
    def fetch_pages_in_source(cls, collection_id=None, db: Session = None):
        # Use the provided database session or get one from the db interface
        db_session = db if db is not None else db_interface.session

        collection_results = Collection.find_by_filter(id=collection_id, db_session=db_session)
        collection = collection_results[0] if collection_results else None

        if collection is None:
            raise ValueError("This source does not exist")

        from sqlalchemy import cast, func
        from sqlalchemy.dialects.postgresql import JSONB

        # Build the query using proper SQLAlchemy syntax for JSON extraction with casting
        query = db_session.query(
            func.distinct(func.jsonb_extract_path_text(cast(MyEmbeddingStore.cmetadata, JSONB), "topic")).label("page"),
            MyCollectionStore.name.label("source"),
        ).join(MyCollectionStore, MyEmbeddingStore.collection_id == MyCollectionStore.uuid)
        if collection.user_id:
            query = query.filter(MyCollectionStore.name == f"{collection.name}_{collection.user_id}")
        else:
            query = query.filter(MyCollectionStore.name == collection.name)

        results = query.all()
        df = pd.DataFrame(results, columns=["page", "source"])
        grouped_df = df.groupby("source")["page"].apply(list).reset_index()
        grouped_df = grouped_df.rename(columns={"page": "pages"})
        result = grouped_df.to_dict(orient="records")

        return result

    @classmethod
    def fetch_confluence_pages_metadata(
        cls, collection_id, source_type: Optional[SourceType] = None, db: Session = None
    ):
        db_to_use = db if db is not None else db_interface.session

        query_filter = (
            db_to_use.query(DocumentLog)
            .distinct()
            .join(Collection, Collection.id == DocumentLog.collection_id)
            .filter(Collection.id == collection_id)
        )
        if source_type:
            query_filter = query_filter.filter(DocumentLog.source_type == source_type)
        query_select = query_filter.order_by(DocumentLog.updated_date.desc()).with_entities(
            DocumentLog.id,
            DocumentLog.identity_constant_name,
            DocumentLog.display_name,
            DocumentLog.version,
            DocumentLog.created_date,
            DocumentLog.updated_date,
            DocumentLog.source_path,
            DocumentLog.source_type,
            DocumentLog.data_source_metadata,
        )
        result = []
        for row in query_select.all():
            # Convert query_select result to dict with named keys
            result.append(
                {
                    "page_id": row.identity_constant_name,
                    "id": row.id,
                    "collection_id": collection_id,
                    "page_name": row.display_name,
                    "version": row.version,
                    "created_date": row.created_date.isoformat() if row.created_date else None,
                    "updated_date": row.updated_date.isoformat() if row.updated_date else None,
                    "source_path": row.source_path,
                    "source_type": row.source_type.value,
                    "public_url": row.data_source_metadata.get("public_url", None),
                }
            )
        return result

    @classmethod
    async def delete_pages_for_source(
        cls,
        collection_id: str,
        source_type: SourceType,
        page_ids: list,
        db: Session = None,
    ):
        db_to_use = db if db is not None else db_interface.session

        page_ids = list(set(page_ids))
        collection = Collection.find_by_filter(id=collection_id, db_session=db_to_use)
        if not collection:
            raise ValueError(f"This confluence source `{collection_id}` does not exist")
        collection = collection[0]
        # Remove physical files from GCP bucket for these pages (only for GCP source_type)
        docs = DocumentLog.find_by_filter(
            db_session=db_to_use,
            collection_id=collection.id,
            source_type=source_type,
            identity_constant_name__in=page_ids,
        )
        for doc in docs:
            gcp_path = doc.url_download
            if gcp_path and doc.source_type == SourceType.GCP:
                try:
                    GCPHelper().delete_file(gcp_path)
                except Exception as e:
                    logger.error(f"Error deleting file from GCP: {e}")
        # Remove document_log records corresponding to these pages (use batch delete)
        page_ids, not_found_page_ids = DocumentLog.get_existing_pages(collection.id, source_type, page_ids)
        if page_ids:
            collection_name = collection.name + "_" + collection.user_id if collection.user_id else collection.name
            doc_retriever = DocumentRetriever.create_doc_retriever(collection_name=collection_name)
            for page_id in page_ids:
                await doc_retriever.remove_documents(page_id)
        DocumentLog.delete_pages(collection.id, page_ids)
        return not_found_page_ids

    @classmethod
    def get_common_source_names(cls, db: Session = None) -> list[Collection]:
        db_to_use = db if db else db_interface.session
        return Collection.get_common_sources_has_note(db_session=db_to_use)

    @classmethod
    def get_source_name_by_user_id(cls, user_id: str, db: Session = None) -> list[Collection]:
        db_to_use = db if db else db_interface.session
        return Collection.find_by_filter(user_id=user_id, db_session=db_to_use)

    @classmethod
    def get_source_by_name_and_user_id(cls, resource_name, user_id: str, db: Session = None) -> list[Collection]:
        db_to_use = db if db else db_interface.session
        return Collection.find_by_filter(name__in=resource_name, user_id=user_id, db_session=db_to_use)

    @classmethod
    def get_source_by_id(cls, resource_id, db: Session = None) -> Collection:
        db_to_use = db if db else db_interface.session
        source = Collection.find_by_filter(id=resource_id, db_session=db_to_use)[0]
        return source

    @staticmethod
    def _delete_gcp_files_for_collection(collection_id, db_session):
        docs = DocumentLog.find_by_filter(db_session=db_session, collection_id=collection_id)
        for doc in docs:
            gcp_path = doc.url_download
            if gcp_path:
                try:
                    GCPHelper().delete_file(gcp_path)
                except Exception as e:
                    print(f"Error deleting file from GCP: {e}")
    @staticmethod
    async def sync_rag_source(collection_id: str) -> ServiceResult:
        result = ServiceResult()

        try:
            collection_model = Collection.find_by_filter(id=collection_id)
            if not collection_model:
                result.error = f"Can't find this collection {collection_id}"
                return result

            collection_model = collection_model[0]
            cronjob_service = CronjobDocumentRag(collection_model)
            return await cronjob_service.process_cronjob_async()

        except ValueError as e:
            result.error = f"Invalid value: {e}"
        except LookupError as e:
            result.error = f"Lookup failed: {e}"
        except RuntimeError as e:
            result.error = f"Runtime error: {e}"

        return result

    @staticmethod
    async def add_gcp_file(
        collection_id: str,
        file_bucket_links: list[str],
        public_view_urls: list[str] | None = None,
        *,
        auto_run_cron_job: bool = True,
    ) -> ServiceResult:
        result = ServiceResult()

        try:
            if not public_view_urls:
                public_view_urls = []

            if len(file_bucket_links) != len(public_view_urls):
                return ServiceResult(
                    error="The length of file_bucket_links and public_view_urls must be the same"
                )

            existing_pages, new_pages = await ManageSource.add_gcp_page(
                file_links=file_bucket_links,
                public_view_urls=public_view_urls,
                collection_id=collection_id,
            )
            if (existing_pages or new_pages) and auto_run_cron_job:
                await ManageSource.sync_rag_source(collection_id)

            result.data = {
                "existing_pages": existing_pages,
                "new_pages": new_pages,
            }
            result.status = ServiceResultEnum.SUCCESS
        except ValueError as e:
            result.error = f"Invalid value: {e}"
        except LookupError as e:
            result.error = f"Lookup failed: {e}"
        except RuntimeError as e:
            result.error = f"Runtime error: {e}"
        return result