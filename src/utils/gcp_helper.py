import logging
import tempfile
from pathlib import Path

from src.config.settings import gcp_bucket_name
from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service

_logger = logging.getLogger(__name__)


class GCPHelper:
    """Helper class for GCP operations."""

    def __init__(self, bucket_name: str = gcp_bucket_name) -> None:
        """Initialize GCP helper.

        Args:
            bucket_name: Name of the GCP bucket to use.

        """
        self.bucket_name = bucket_name
        self.storage_client = gcp_bucket_service.client
        self.bucket = self.storage_client.bucket(bucket_name)

    def parse_gcp_path(self, gcp_path: str) -> tuple[str, str]:
        """Parse GCP path to get bucket name and file path.

        Args:
            gcp_path: Full GCP path (e.g. https://storage.cloud.google.com/bucket-name/path/to/file)

        Returns:
            Tuple of (bucket_name, file_path)

        Raises:
            ValueError: If GCP path is invalid

        """
        expected_parts = 2
        try:
            path_parts = gcp_path.replace("https://storage.cloud.google.com/", "").split("/", 1)
            if len(path_parts) != expected_parts:
                error_msg = "Invalid GCP path format. Must contain bucket name and file path"
                raise ValueError(error_msg)
            return path_parts[0], path_parts[1]
        except Exception as e:
            error_msg = f"Error parsing GCP path: {e!s}"
            raise ValueError(error_msg) from e

    def download_file(self, gcp_path: str, local_dir: str | None = None) -> str:
        """Download file from GCP bucket to local directory.

        Args:
            gcp_path: Full GCP path to the file
            local_dir: Local directory to save the file. If None, will use temp directory

        Returns:
            str: Local path to the downloaded file

        Raises:
            ValueError: If GCP path is invalid
            Exception: If download fails

        """
        try:
            # Parse GCP path
            bucket_name, file_path = self.parse_gcp_path(gcp_path)

            # Verify bucket name matches
            if bucket_name != self.bucket_name:
                error_msg = f"Bucket name mismatch. Expected {self.bucket_name}, got {bucket_name}"
                raise ValueError(error_msg)

            # Get blob
            blob = self.bucket.blob(file_path)

            # Create local directory if not exists
            if local_dir is None:
                local_dir = tempfile.mkdtemp()
            else:
                Path(local_dir).mkdir(parents=True, exist_ok=True)

            # Get filename from path
            file_name = Path(file_path).name
            local_file_path = Path(local_dir) / file_name

            # Download file
            blob.download_to_filename(str(local_file_path))

            _logger.info(f"Successfully downloaded file from {gcp_path} to {local_file_path}")
            return str(local_file_path)

        except Exception as e:
            _logger.error(f"Error downloading file from {gcp_path}: {e!s}")
            raise

    def upload_file(self, local_file_path: str, user_id: str, collection_name: str) -> str:
        """Upload file to GCP bucket.

        Args:
            local_file_path: Local path to the file to upload
            user_id: User ID for organizing files in the bucket
            collection_name: Collection name for organizing files in the bucket

        Returns:
            str: URL to the uploaded file in GCP bucket

        Raises:
            Exception: If upload fails

        """
        try:
            # Get filename
            file_name = Path(local_file_path).name

            # Create destination path
            fixed_path = "files"
            destination_path = f"{fixed_path}/{user_id}/{collection_name}/{file_name}"

            # Create blob and upload
            blob = self.bucket.blob(destination_path)
            blob.upload_from_filename(local_file_path)

            # Generate URL
            url = f"https://storage.cloud.google.com/{self.bucket_name}/{destination_path}"

            _logger.info(f"Successfully uploaded file {file_name} to {url}")
            return url

        except Exception as e:
            _logger.error(f"Error uploading file '{local_file_path}': {e!s}")
            raise

    def delete_file(self, gcp_path: str) -> bool:
        """Delete file from GCP bucket.

        Args:
            gcp_path: Full GCP path to the file

        Returns:
            bool: True if deletion successful, False otherwise

        Raises:
            ValueError: If GCP path is invalid

        """
        try:
            # Parse GCP path
            bucket_name, file_path = self.parse_gcp_path(gcp_path)

            # Verify bucket name matches
            if bucket_name != self.bucket_name:
                error_msg = f"Bucket name mismatch. Expected {self.bucket_name}, got {bucket_name}"
                raise ValueError(error_msg)

            # Delete blob
            blob = self.bucket.blob(file_path)
            blob.delete()

            _logger.info(f"Successfully deleted file from {gcp_path}")
            return True

        except Exception as e:
            _logger.error(f"Error deleting file from {gcp_path}: {e!s}")
            return False

    def get_file_metadata(self, gcp_path: str) -> dict:
        """Get metadata of a file in GCP bucket.

        Args:
            gcp_path: Full GCP path to the file

        Returns:
            dict: File metadata including size, content_type, etc.

        Raises:
            ValueError: If GCP path is invalid

        """
        try:
            # Parse GCP path
            bucket_name, file_path = self.parse_gcp_path(gcp_path)

            # Verify bucket name matches
            if bucket_name != self.bucket_name:
                error_msg = f"Bucket name mismatch. Expected {self.bucket_name}, got {bucket_name}"
                raise ValueError(error_msg)

            # Get blob metadata
            blob = self.bucket.blob(file_path)
            blob.reload()  # Ensure we have the latest metadata

            return {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "created": blob.time_created,
                "updated": blob.updated,
                "md5_hash": blob.md5_hash,
            }

        except Exception as e:
            _logger.error(f"Error getting metadata for {gcp_path}: {e!s}")
            raise

    def _get_content_type(self, file_name: str) -> str:
        """Get content type based on file extension.

        Args:
            file_name: Name of the file

        Returns:
            str: Content type of the file

        """
        path = Path(file_name)
        extension = path.suffix.lower()
        content_types = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".json": "application/json",
            ".csv": "text/csv",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
        }
        return content_types.get(extension, "application/octet-stream")
