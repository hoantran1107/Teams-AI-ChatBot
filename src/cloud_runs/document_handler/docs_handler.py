import asyncio
import logging
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import anyio
import google.auth

from src.config.environment import env
from src.constants.docling_constant import DoclingConstant, DoclingException
from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service
from src.utils.file_helper import helper_convert_file_to_markdown_async

_logger = logging.getLogger(__name__)

logging.getLogger("pdfminer").setLevel(logging.ERROR)


class UnsupportedFileTypeError(Exception):
    """Exception raised for unsupported file types."""

def is_supported_file(file_path: str) -> bool:
    """Check if the file type is supported.

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file type is supported, False otherwise

    """
    file_ext = Path(file_path).suffix.lower()
    return file_ext in DoclingConstant.SUPPORTED_FILES


def start_up_file_to_gcp_bucket(file_name: str, file_path: str, user_id: str, collection_name: str) -> str:
    """Upload file to a GCP bucket.

    Args:
        file_name: Name of the file to store in the bucket
        file_path: Local path to the file to upload
        user_id: User ID for organizing files in the bucket
        collection_name: Collection name for organizing files in the bucket

    Returns:
        URL to the uploaded file in GCP bucket

    """
    # Initialize client
    bucket_name = env.get_str("GCP_BUCKET_NAME", "ifdcpb-rag-store")
    _, project_id = google.auth.default()
    print(f"Project ID: {project_id}")
    storage_client = gcp_bucket_service.client
    # Reference to bucket
    bucket = storage_client.bucket(bucket_name)

    # Fixed path
    fixed_path = "files"

    # Destination path in the bucket
    destination_path = f"{fixed_path}/{user_id}/{collection_name}/{file_name}"

    # Create blob
    blob = bucket.blob(destination_path)

    # Upload file
    try:
        blob.upload_from_filename(file_path)

        url = f"https://storage.cloud.google.com/{bucket_name}/{destination_path}"
        return url

    except Exception:
        msg = f"Failed to upload file '{file_name}' to GCP bucket '{bucket_name}' at path '{destination_path}'"
        _logger.error(msg)
        raise


async def download_file_from_gcp_async(gcp_path: str, local_dir: str | None = None) -> str:
    """Download file from GCP bucket to local directory.

    Args:
        gcp_path: Full GCP path (e.g. https://storage.cloud.google.com/bucket-name/path/to/file)
        local_dir: Local directory to save the file. If None, will use temp directory

    Returns:
        str: Local path to the downloaded file

    Raises:
        ValueError: If GCP path is invalid
        Exception: If download fails

    """
    try:
        # Parse GCP path to get bucket name and file path
        # if not gcp_path.startswith('https://storage.cloud.google.com/'):
        # 	raise ValueError("Invalid GCP path format. Must start with https://storage.cloud.google.com/")

        # # Remove the base URL to get bucket and file path
        path_parts = gcp_path.replace("https://storage.cloud.google.com/", "").split("/", 1)
        if len(path_parts) != 2:
            msg = "Invalid GCP path format. Must contain bucket name and file path"
            raise ValueError(msg)

        bucket_name = path_parts[0]
        file_path = path_parts[1]

        # Initialize GCP client
        storage_client = gcp_bucket_service.client
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)

        # Create local directory if not exists
        if local_dir is None:
            local_dir = tempfile.mkdtemp()
        else:
            Path(local_dir).mkdir(parents=True, exist_ok=True)

        # Get filename from path
        file_name = Path(file_path).name
        local_file_path = Path(local_dir) / file_name

        # Download file
        _ = await asyncio.get_running_loop().run_in_executor(
            ThreadPoolExecutor(max_workers=1),
            blob.download_to_filename,
            str(local_file_path),
        )

        _logger.info(f"Successfully downloaded file from {gcp_path} to {local_file_path}")
        return str(local_file_path)

    except Exception as e:
        _logger.error(f"Error downloading file from {gcp_path}: {e!s}")
        raise


async def convert_gcp_file_to_markdown_async(message_data: dict[str, Any]):
    """Convert a file from GCP to Markdown and upload back to GCP bucket.

    Args:
        message_data: Dictionary containing:
            - gcp_path: Full GCP path to the file
            - user_id: User ID for organizing files in the bucket
            - collection_name: Collection name for organizing files in the bucket

    Returns:
        URL to the uploaded Markdown file in GCP bucket

    """
    local_file_path = None
    temp_markdown_path = None
    try:
        start_time = time.time()

        # Extract data from message
        gcp_path = str(message_data.get("gcp_path"))
        user_id = str(message_data.get("user_id"))
        collection_name = str(message_data.get("collection_name"))

        if not all([gcp_path, user_id, collection_name]):
            msg = "Missing required fields in message_data: gcp_path, user_id, or collection_name"
            raise ValueError(msg)

        # Download file from GCP
        local_file_path = await download_file_from_gcp_async(gcp_path)

        # Check if the file is supported
        if not is_supported_file(local_file_path):
            msg = f"Unsupported file type: {Path(local_file_path).suffix}"
            raise UnsupportedFileTypeError(msg)

        # Convert the file to Markdown
        start_time = time.time()
        try:
            result = await helper_convert_file_to_markdown_async(local_file_path)
        except DoclingException as e:
            # DoclingException already contains UnsupportedFileTypeError
            _logger.error("Docling conversion failed for %s: %s", Path(local_file_path).name, str(e))
            raise UnsupportedFileTypeError(str(e))
        except Exception as e:
            # Handle other conversion errors - error will be passed to frontend for AI processing
            error_message = str(e)
            _logger.error(error_message)
            raise UnsupportedFileTypeError(error_message)
        
        end_time = time.time() - start_time
        _logger.info(f"Document {local_file_path}converted in {end_time:.2f} seconds.")

        # Create output Markdown file name
        original_filename = Path(local_file_path).name
        markdown_filename = Path(original_filename).stem + ".md"
        temp_markdown_path = Path(local_file_path).parent / markdown_filename

        # Write Markdown content to file
        async with await anyio.open_file(temp_markdown_path, "w", encoding="utf-8") as f:
            await f.write(result)

        # Upload the Markdown file to GCP bucket
        # Run sync function in thread pool to avoid event loop issues
        gcp_url = await asyncio.get_running_loop().run_in_executor(
            ThreadPoolExecutor(max_workers=1),
            start_up_file_to_gcp_bucket,
            markdown_filename,
            str(temp_markdown_path),
            user_id,
            collection_name,
        )

        elapsed_time = time.time() - start_time
        _logger.info(f"Time taken to process file: {elapsed_time} seconds")
        return gcp_url

    except Exception as e:
        _logger.error(f"Error processing document: {e!s}")
        raise
    finally:
        # Cleanup temporary files
        if local_file_path and Path(local_file_path).exists():
            Path(local_file_path).unlink()
        if temp_markdown_path and Path(temp_markdown_path).exists():
            Path(temp_markdown_path).unlink()
