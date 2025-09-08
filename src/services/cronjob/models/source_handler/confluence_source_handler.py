from typing import Dict, List

from src.services.confluence_service.services.confluence_service import ConfluenceService
from src.services.cronjob.models.source_handler import BaseSourceHandler, DocumentMetadata
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import SourceType


class ConfluenceSourceHandler(BaseSourceHandler):
    def __init__(self, source_path: str, **config):
        super().__init__(source_path, SourceType.CONFLUENCE, **config)
        self.base_url = source_path.rstrip("/")
        self.auth = (config.get("username"), config.get("password"))
        self.space_keys = config.get("space_keys", [])
        self.collection_id = config.get("collection_id")
        assert self.collection_id, "Collection ID is required for Confluence source"

    async def list_new_updated_delete_docs(self, **filters) -> Dict[str, List[DocumentMetadata]]:
        """List all pages from Confluence spaces"""
        confluence_service = ConfluenceService(collection_id=self.collection_id)
        changes_docs = await confluence_service.get_changes_pages(self.work_dir)

        return changes_docs
