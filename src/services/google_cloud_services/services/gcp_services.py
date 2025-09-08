import hashlib
import asyncio
import logging
import os
import re
from typing import Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
from google.cloud import storage
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient


from src.services.postgres.models.downloaded_file import DownloadedFile
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import (
    Collection,
    SourceType,
)
from src.config.environment import env

_logger = logging.getLogger("GCPBucketService")


class GCPBucketService:
    """Service class to interact with Google Cloud Storage bucket."""

    def __init__(self) -> None:
        # Initialize GCP client and bucket
        self.client = storage.Client(project=env.get_str("GCP_PROJECT_NAME", "InfraTeam Playground"))
        self.bucket = self.client.bucket(
            env.get_str("GCP_BUCKET_NAME", "ifdcpb-rag-store")
        )

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize file path by removing excess slashes and leading/trailing slashes."""
        if path:
            return re.sub(r"/+", "/", path).strip("/")
        return path

    def download_file_from_gcp_bucket(
        self, file_name: str, destination_dir: str | None = None
    ) -> Optional[str]:
        """Download a file from GCP bucket to local directory."""
        try:
            # Set default download directory if not provided
            if destination_dir is None:
                destination_dir = "downloads"
            os.makedirs(destination_dir, exist_ok=True)

            # Use only the base file name for destination
            base_file_name = os.path.basename(file_name)
            destination_file_name = os.path.join(destination_dir, base_file_name)

            # Normalize file path and download
            blob_path = self._normalize_path(file_name)
            blob = self.bucket.blob(blob_path)
            blob.download_to_filename(destination_file_name)
            return destination_file_name
        except Exception as e:
            # Log critical errors for debugging
            _logger.error(f"Download failed for {file_name}: {e}")
            return None

    async def upload_file_to_gcp_bucket_async(self, source_file_name, destination_file_name):
        """Upload a file to the GCP bucket."""
        try:
            destination_file_name = self._normalize_path(destination_file_name)
            blob = self.bucket.blob(destination_file_name)
            with ThreadPoolExecutor(max_workers=1) as executor:
                res = await asyncio.get_running_loop().run_in_executor(
                    executor,
                    blob.upload_from_filename,
                    source_file_name,
                )
            _logger.info(f"Upload result: {res}")
            _logger.info(f"File {source_file_name} uploaded to {destination_file_name}")
        except Exception as e:
            _logger.error(f"Error uploading file {source_file_name}: {e}")
            raise e

    def delete_file_from_gcp_bucket(self, file_name: str) -> None:
        """Delete a file from GCP bucket."""
        try:
            # Normalize file path and delete
            file_name = self._normalize_path(file_name)
            blob = self.bucket.blob(file_name)
            blob.delete()
            _logger.info(f"File {file_name} deleted.")
        except Exception as e:
            # Log critical errors for debugging
            _logger.error(f"Delete failed for {file_name}: {e}")

    def stream_file_from_gcp_bucket(self, file_name: str) -> Optional[bytes]:
        """Stream file content from GCP bucket as bytes."""
        try:
            # Normalize file path and stream content
            file_name = self._normalize_path(file_name)
            blob = self.bucket.blob(file_name)
            return blob.download_as_string()
        except Exception as e:
            # Log critical errors for debugging
            _logger.error(f"Stream failed for {file_name}: {e}")
            return None

    def get_list_files_in_gcp_bucket(
        self, prefix: str, save_to_dir: str
    ) -> List[DownloadedFile]:
        """List all files in GCP bucket under a given prefix."""
        try:
            # Normalize prefix and list files
            prefix = self._normalize_path(prefix)
            blobs = self.bucket.list_blobs(prefix=prefix)

            results = []
            for blob in blobs:
                if blob.size == 0:
                    continue
                downloaded_path = self.download_file_from_gcp_bucket(
                    blob.name, destination_dir=save_to_dir
                )
                if downloaded_path:
                    with open(downloaded_path, "rb") as f:
                        content_bytes = f.read()
                    results.append(
                        DownloadedFile(
                            identity_constant_name=blob.name,
                            display_file_name=blob.name,
                            size=blob.size,
                            content_type=blob.content_type,
                            public_url=blob.public_url,
                            time_created=blob.time_created,
                            updated=blob.updated,
                            version=None,
                            source_type=SourceType.GCP,
                            contents=content_bytes,
                            content_hash=hashlib.md5(content_bytes).hexdigest(),
                            downloaded_path=downloaded_path,
                        )
                    )

            return results
        except Exception as e:
            # Log critical errors for debugging
            _logger.error(f"List failed for prefix {prefix}: {e}")
            return []

    @classmethod
    def check_source_name(cls, source_name: str) -> Collection | None:
        collections = Collection.find_by_filter(
            name=source_name, source_type=SourceType.GCP
        )
        if collections:
            return collections[0]
        return None


class GooglePubSubService:
    """Service class to interact with Google Cloud Pub/Sub."""

    def __init__(self):
        self.open_pubsub_client()

    def open_pubsub_client(self) -> None:
        """Open pubsub client."""
        self.pub_client = PublisherClient()
        self.sub_client = SubscriberClient()

    def get_publisher_client(self) -> PublisherClient:
        return self.pub_client

    def get_subscriber_client(self) -> SubscriberClient:
        return self.sub_client

    def publish(self, pub_topic_id: str, message: bytes) -> Any:
        """Publish a message to a pubsub topic."""
        topic_path = self.pub_client.topic_path(
            "infrateam-playground", pub_topic_id
        )  # noqa
        attributes = {"Content-Type": "application/json; charset=utf-8"}
        future = self.pub_client.publish(topic=topic_path, data=message, **attributes)
        print("result: ", future.result())
        return future


gcp_bucket_service = GCPBucketService()
