from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import DocumentLog, SourceType


@dataclass
class DocumentMetadata:
    """Metadata for a document from any source."""

    db_instance: DocumentLog
    identity_constant_name: str
    display_name: str
    content_hash: str
    size: int | None
    content_type: str | None
    version: str | None
    source_metadata: dict
    content: bytes | None = None
    download_url: str | None = None


class BaseSourceHandler(ABC):
    """Abstract base class for all source handlers."""

    def __init__(self, source_path: str, source_type: "SourceType", work_dir: str, **config):
        self.source_path = source_path
        self.source_type = source_type
        self.config = config
        self.work_dir = work_dir

    @abstractmethod
    async def list_new_updated_delete_docs(self, **filters) -> dict[str, list[DocumentMetadata]]:
        """List all documents from source."""

    @staticmethod
    def should_sync_document(remote_doc: DocumentMetadata, existing_doc: "DocumentLog | None") -> bool:
        """Determine if document needs syncing."""
        if not existing_doc:
            return True

        # Check content hash
        if existing_doc.content_hash != remote_doc.content_hash:
            return True

        # Check version if available
        if remote_doc.version and str(existing_doc.version) != str(remote_doc.version):
            return True

        return False

    def prepare_document_data(self, metadata: DocumentMetadata, collection_id: int) -> dict:
        """Prepare document data for database."""
        return {
            "identity_constant_name": metadata.identity_constant_name,
            "display_name": metadata.display_name,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "collection_id": collection_id,
            "document_size": metadata.size,
            "content_type": metadata.content_type,
            "content_hash": metadata.content_hash,
            "version": metadata.version,
            "source_metadata": metadata.source_metadata,
            "url_download": metadata.download_url,
        }
