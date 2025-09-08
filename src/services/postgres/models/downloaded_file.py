from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import SourceType


class DownloadedFile(BaseModel):
	size: Optional[int]
	identity_constant_name: str
	display_file_name: str
	content_type: Optional[Any]
	public_url: str
	time_created: Optional[datetime] = Field(datetime.now())
	updated: Optional[datetime] = Field(datetime.now())
	version: Optional[Any] = Field(None)
	source_type: SourceType
	contents: bytes
	content_hash: Any
	downloaded_path: str
