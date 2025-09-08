import logging
from datetime import datetime

from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import Collection, DocumentLog, SyncLog

_logger = logging.getLogger("DocumentRag")


class DocumentRag:
    """Class to manage document logging in PostgreSQL for RAG."""

    def __init__(self, collection: Collection):
        """Initialize DocumentRag with a collection."""
        self.collection_id = collection.id

    def update_sync_time(self, notes: str | None = None):
        """Update sync time for the collection_id."""
        _logger.info("Updating sync time")
        return SyncLog.create(collection_id=self.collection_id, notes=notes)

    def upsert_files(self, files, notes: str | None = None):
        """Upsert files into document_log table."""
        current_time = datetime.now()

        def metadata(file):
            _metadata = {
                "content_type": file.get("content_type"),
                "document_size": file.get("document_size"),
            }
            # remove None values
            _metadata = {k: v for k, v in _metadata.items() if v is not None}
            return _metadata

        # Get existing documents with the same identity_constant_name and collection_id
        identity_names = [file["identity_constant_name"] for file in files]
        existing_docs = DocumentLog.find_by_filter(
            collection_id=self.collection_id,
            identity_constant_name__in=identity_names,
        )
        # Create a dictionary of existing documents for fast lookup
        existing_map = {(doc.identity_constant_name, doc.collection_id): doc for doc in existing_docs}
        # Prepare data for insertion - only include new documents
        new_docs = []
        for file in files:
            key = (file["identity_constant_name"], self.collection_id)
            if key not in existing_map:
                new_docs.append(
                    {
                        "identity_constant_name": file["identity_constant_name"],
                        "display_name": file["display_name"],
                        "content_hash": file["content_hash"],
                        "collection_id": self.collection_id,
                        "url_download": file.get("url_download"),
                        "created_date": file.get("created_date", current_time),
                        "updated_date": file.get("updated_date", current_time),
                        "version": file.get("version"),
                        "data_source_metadata": metadata(file),
                    },
                )
        # Bulk insert only new documents
        if new_docs:
            document_log = DocumentLog()
            document_log.bulk_insert(new_docs)
        # Update existing documents individually
        for file in files:
            key = (file["identity_constant_name"], self.collection_id)
            if key in existing_map:
                doc = existing_map[key]
                doc.display_name = file["display_name"]
                doc.content_hash = file["content_hash"]
                doc.url_download = file.get("url_download")
                doc.updated_date = file.get("updated_date", current_time)
                doc.version = file.get("version")
                doc.data_source_metadata = metadata(file)
                doc.save()
        self.update_sync_time(notes)

    def fetch_doc_logs(self):
        """Fetch all documents for the given collection_id."""
        return DocumentLog.get_by_collection_id(self.collection_id)

    def delete_files(self, file_names: list[str], notes: str | None = None):
        """Delete files from document_log table."""
        DocumentLog.delete_by_names_and_collection_id(file_names, self.collection_id)
        self.update_sync_time(notes)
