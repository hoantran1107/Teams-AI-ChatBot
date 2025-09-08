import asyncio
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Tuple
from urllib.parse import urlparse, quote

from src.config.settings import gcp_bucket_name
from src.services.cronjob.models.source_handler import (
    BaseSourceHandler,
    DocumentMetadata,
)
from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import (
    DocumentLog,
    SourceType,
)

_logger = logging.getLogger("GCPSourceHandler")

GCS_EXECUTOR = ThreadPoolExecutor(max_workers=2)


@dataclass
class GCSFileMetadata:
    """Metadata of a file on Google Cloud Storage."""

    name: str  # Blob name (full path)
    size: int  # File size (bytes)
    content_type: str  # MIME type
    created: datetime  # Creation time
    updated: datetime  # Update time
    md5_hash: str  # MD5 hash of the file
    folder: str  # Full folder path containing the file
    file: str  # File name
    bucket_folder_path: str  # Bucket folder that contains the file
    version: int  # Unique identifier for each version
    user_id: str  # User ID from the path
    collection: str  # Collection name from the path
    metageneration: int | None = None  # Number of times metadata has been updated
    etag: str | None = None  # Entity tag for the object

    @property
    def extension(self) -> str:
        """Get the file extension."""
        parts = self.file.split(".")
        return f".{parts[-1]}" if len(parts) > 1 else ""

    @property
    def size_mb(self) -> float:
        """File size in MB."""
        return self.size / (1024 * 1024)

    @property
    def size_readable(self) -> str:
        """File size in readable format (KB, MB, GB)."""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size / (1024 * 1024 * 1024):.1f} GB"

    @property
    def age_days(self) -> int:
        """Number of days since the file was created."""
        return (datetime.now(self.created.tzinfo) - self.created).days

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "size": self.size,
            "size_readable": self.size_readable,
            "content_type": self.content_type,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "md5_hash": self.md5_hash,
            "folder": self.folder,
            "file": self.file,
            "extension": self.extension,
            "age_days": self.age_days,
            "version": self.version,
            "metageneration": self.metageneration,
            "etag": self.etag,
            "bucket_folder_path": self.bucket_folder_path,
            "user_id": self.user_id,
            "collection": self.collection,
        }


def parse_gcs_url(url: str) -> Tuple[str, str, str, str, str, str]:
    """Parse a Google Cloud Storage URL into its components.

    Expected pattern: https://storage.cloud.google.com/bucket/files/user_id/collection/file.ext

    Args:
        url: GCS URL (e.g., https://storage.cloud.google.com/ifdcpb-rag-store/files/tien-test/collection1/Doc1.docx)

    Returns:
        Tuple of (bucket_name, folder_name, file_name, blob_name, user_id, collection)

    Raises:
        ValueError: If the URL is not a valid GCS URL or does not contain the required components.

    """
    parsed = urlparse(url)

    # Check domain
    if parsed.netloc != "storage.cloud.google.com":
        raise ValueError(f"URL is not a Google Cloud Storage URL: {url}")

    # Split path - remove leading slash and split into bucket and the rest
    path = parsed.path.strip("/")
    parts = path.split("/", 1)

    if len(parts) < 2:
        raise ValueError(f"URL does not contain enough components (bucket/folder/file): {url}")

    bucket_name = parts[0]
    blob_name = parts[1]  # The rest after the bucket name

    # Split blob_name into components
    blob_parts = blob_name.split("/")

    # Expected structure: files/user_id/collection/file.ext
    if len(blob_parts) < 4:
        raise ValueError(f"URL must contain files/user_id/collection/file structure, got: {blob_name}")

    # Validate first part is "files"
    if blob_parts[0] != "files":
        raise ValueError(f"URL path must start with 'files', got: '{blob_parts[0]}'")

    user_id = blob_parts[1]
    collection = blob_parts[2]
    file_name = "/".join(blob_parts[3:])  # Support nested files if any

    # Full folder path
    folder_name = "/".join(blob_parts[:-1])

    return bucket_name, folder_name, file_name, blob_name, user_id, collection


def normalize_url(url: str) -> str:
    """Normalize a URL."""
    return quote(url, safe=":/")


def validate_gcs_url(url: str) -> None:
    """Validate a Google Cloud Storage (GCS) URL according to the following requirements:
    - The bucket name must be 'ifdcpb-rag-store'
    - The URL must follow pattern: /files/user_id/collection/file.doc(x)
    - The file must have a .doc or .docx extension

    Args:
        url: The GCS URL to validate.

    Raises:
        AssertionError: If the URL is invalid or does not meet the requirements.

    """
    # Parse URL and extract components
    try:
        bucket_name, _, file_name, _, user_id, collection = parse_gcs_url(url)
    except ValueError as e:
        raise AssertionError(str(e))

    # Validate bucket name
    assert bucket_name == gcp_bucket_name, f"Bucket name must be 'ifdcpb-rag-store', got: '{bucket_name}'"

    # Validate user_id exists
    assert user_id, "URL must contain a user_id"

    # Validate collection exists
    assert collection, "URL must contain a collection"

    # Validate file exists
    assert file_name, "URL must contain a file name"

    # Validate file extension is .doc or .docx
    valid_extensions = [".doc", ".docx", "md"]
    file_ext = None

    for ext in valid_extensions:
        if file_name.lower().endswith(ext):
            file_ext = ext
            break

    assert file_ext is not None, f"File must have a .doc or .docx extension, got: '{file_name}'"


def file_bucket_hash_name(file_name):
    return uuid.uuid5(uuid.NAMESPACE_DNS, file_name).hex


async def get_metadata_with_validation(url: str) -> GCSFileMetadata:
    """
    Get metadata with validation

    Args:
        url: The GCS URL to validate and fetch metadata for.

    Returns:
        GCSFileMetadata: Metadata of the file if validation passes.

    Raises:
        AssertionError: If the URL is invalid or does not meet requirements.
    """
    # Validate URL first
    validate_gcs_url(url)

    # Parse URL
    bucket_name, folder_name, file_name, blob_name, user_id, collection = parse_gcs_url(url)

    # Get metadata
    def get_metadata_sync():
        client = gcp_bucket_service.client
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.reload()

        # Return dataclass instance
        return GCSFileMetadata(
            name=file_bucket_hash_name(blob.name),
            size=blob.size or 0,
            content_type=blob.content_type or "application/octet-stream",
            created=blob.time_created or datetime.now(),
            updated=blob.updated or datetime.now(),
            md5_hash=blob.md5_hash or "",
            folder=folder_name,
            file=file_name,
            bucket_folder_path=f"{bucket_name}/{folder_name}",
            version=blob.generation or 0,
            user_id=user_id,
            collection=collection,
            metageneration=blob.metageneration,
            etag=blob.etag,
        )

    result = await asyncio.get_event_loop().run_in_executor(GCS_EXECUTOR, lambda x: get_metadata_sync(), None)

    return result


async def download_gcs_file(url: str, work_dir: str, file_name) -> str:
    """
    Download the file from the GCS URL to the local directory

    Args:
        url: GCS URL (e.g., https://storage.cloud.google.com/ifdcpb-rag-store/files/user_id/collection/file.docx)
        work_dir: Local directory to save the file
        file_name: filename to save the file (include extension)

    Returns:
        str: Path to the downloaded file

    Raises:
        AssertionError: If URL is invalid
        NotFound: If the file is not found in the bucket
        Exception: If download fails
    """
    # Validate URL first
    validate_gcs_url(url)

    # Parse URL
    bucket_name, _, _, blob_name, *_ = parse_gcs_url(url)

    # Save directly in work_dir with just the filename
    dest_path = os.path.join(work_dir, file_name)

    # Download file
    def download_sync(dest_path):
        client = gcp_bucket_service.client
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(dest_path)

    await asyncio.get_event_loop().run_in_executor(GCS_EXECUTOR, download_sync, dest_path)
    _logger.info(f"Downloaded file to {dest_path}")

    return dest_path


async def list_files_in_collection(user_id: str, collection: str) -> dict[str, GCSFileMetadata]:
    """List all files in a specific collection for a user.

    Args:
        user_id: User ID
        collection: Collection name

    Returns:
        Dict[str, GCSFileMetadata]: Dictionary of file metadata objects

    """

    def list_files_sync():
        client = gcp_bucket_service.client
        bucket_name = gcp_bucket_name
        bucket = client.bucket(bucket_name)

        # Construct prefix: files/user_id/collection/
        prefix = f"files/{user_id}/{collection}/"

        metadata_list = dict()

        # List all blobs with the prefix
        for blob in bucket.list_blobs(prefix=prefix):
            # Skip if it's just the folder (no actual file)
            if blob.name.endswith("/"):
                continue

            # Extract file name from blob name
            parts = blob.name.split("/")
            if len(parts) >= 4:  # files/user_id/collection/filename
                file_name = "/".join(parts[3:])  # Support nested files

                # Only include .doc and .docx files
                if file_name.lower().endswith(".md"):
                    folder_name = "/".join(parts[:-1])

                    identity_constant_name = file_bucket_hash_name(blob.name)
                    metadata = GCSFileMetadata(
                        name=identity_constant_name,
                        size=blob.size or 0,
                        content_type=blob.content_type or "application/octet-stream",
                        created=blob.time_created,
                        updated=blob.updated,
                        md5_hash=blob.md5_hash or "",
                        folder=folder_name,
                        file=file_name,
                        bucket_folder_path=f"{bucket_name}/{folder_name}",
                        version=blob.generation,
                        user_id=user_id,
                        collection=collection,
                        metageneration=blob.metageneration,
                        etag=blob.etag,
                    )
                    metadata_list[identity_constant_name] = metadata

        return metadata_list

    result = await asyncio.get_event_loop().run_in_executor(GCS_EXECUTOR, lambda x: list_files_sync(), None)

    return result


class GCPSourceHandler(BaseSourceHandler):
    def __init__(self, source_path: str, **config):
        super().__init__(source_path, SourceType.GCP, **config)
        self.collection_id = config.get("collection_id")
        assert self.collection_id, "Collection ID is required for GCP source"

    async def list_new_updated_delete_docs(self, **filters) -> dict[str, list[DocumentMetadata]]:
        """List all documents in GCS bucket under prefix."""
        document_logs = DocumentLog.get_by_collection_and_source(
            collection_id=self.collection_id,
            source_type=SourceType.GCP,
            source_path=self.source_path,
        )
        if not document_logs:
            return dict(news=[], updates=[], deletes=[])

        user_id = document_logs[0].data_source_metadata["user_id"]
        collection = document_logs[0].data_source_metadata["collection"]

        # collect all new metadata for others from the cloud
        file_remote_metadata = await list_files_in_collection(collection=collection, user_id=user_id)

        # check deleted docs
        deleted_docs = [doc for doc in document_logs if doc.identity_constant_name not in file_remote_metadata]
        remain_docs = [doc for doc in document_logs if doc.identity_constant_name in file_remote_metadata]

        # check new docs
        new_docs = [doc for doc in remain_docs if doc.is_new_doc]

        # check existing docs
        existing_docs = [doc for doc in remain_docs if not doc.is_new_doc]

        # check doc that needs to be updated in existing docs
        updated_docs = []
        for doc in existing_docs:
            remote_doc_metadata = file_remote_metadata[doc.identity_constant_name]
            need_updated = (
                remote_doc_metadata.version != doc.version and remote_doc_metadata.md5_hash != doc.content_hash
            )
            if need_updated:
                updated_docs.append(doc)

        # convert all docs in each type change to DocumentMetadata
        async def convert_doc_to_metadata(doc: DocumentLog, is_remove=False) -> DocumentMetadata:
            remote_metadata = None
            file_local_url = None

            if not is_remove:
                remote_metadata = file_remote_metadata[doc.identity_constant_name]
                extension_file = doc.display_name.split(".")[-1]
                file_download_name = f"{doc.identity_constant_name}.{extension_file}"
                file_local_url = await download_gcs_file(doc.url_download, self.work_dir, file_download_name)

            return DocumentMetadata(
                db_instance=doc,
                identity_constant_name=doc.identity_constant_name,
                display_name=getattr(remote_metadata, "file", doc.display_name),
                size=getattr(remote_metadata, "size", None),
                content_type=getattr(remote_metadata, "content_type", None),
                version=str(remote_metadata.version) if remote_metadata else doc.version,
                content_hash=getattr(remote_metadata, "md5_hash", doc.content_hash),
                download_url=file_local_url,
                source_metadata={
                    "updated_date": getattr(remote_metadata, "updated", None),
                    "public_url": normalize_url(doc.data_source_metadata.get("public_url", doc.url_download)),
                },
            )

        return {
            "news": [await convert_doc_to_metadata(doc) for doc in new_docs],
            "updates": [await convert_doc_to_metadata(doc) for doc in updated_docs],
            "deletes": [await convert_doc_to_metadata(doc, is_remove=True) for doc in deleted_docs],
        }
