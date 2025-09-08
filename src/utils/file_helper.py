import logging
import time
from datetime import UTC, datetime
from json import loads
from pathlib import Path

from botbuilder.core import TurnContext

from src.config.environment import env
from src.constants.docling_constant import DoclingException
from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service
from src.utils.msword_helper import convert_doc_to_docx
from src.utils.websocket_helper import convert_file_via_docling_websocket_subscription

_logger = logging.getLogger(__name__)


def get_creation_time(file_path: str) -> str:
    """Return the creation time of the given file path."""
    return datetime.fromtimestamp(Path(file_path).stat().st_birthtime, tz=UTC).isoformat()


def get_modification_time(file_path: str) -> str:
    """Return the modification time of the given file path."""
    return datetime.fromtimestamp(Path(file_path).stat().st_mtime, tz=UTC).isoformat()


def get_file_name(file_path: str) -> str:
    """Return the file name with extension from the given file path."""
    return Path(file_path).name


def get_file_stem(file_path: str) -> str:
    """Return the file name without extension from the given file path."""
    return Path(file_path).stem


def convert_doc_to_docx_in_folder(folder_path: str) -> dict[str, str] | None:
    """Convert DOC files in a folder to DOCX format.

    Args:
        folder_path: Path to folder containing DOC files to convert

    Returns:
        dict[str, str] | None: Dictionary mapping file names (without extension) to their full paths,
        or None if no DOC files found

    """
    path_dir = Path(folder_path)
    output_dir = path_dir
    doc_files = list(path_dir.glob("*.doc"))
    if not doc_files:
        _logger.warning(f"No DOC files found in {path_dir}")
        return None

    _logger.info(f"Found {len(doc_files)} DOC files to convert")

    success_count = 0
    for doc_file in doc_files:
        if convert_doc_to_docx(str(doc_file), str(output_dir)):
            success_count += 1
            # remove the original doc file
            try:
                doc_file.unlink()
            except OSError as e:
                _logger.error(f"Failed to remove {doc_file}: {e}")

    _logger.info(
        f"Conversion completed: {success_count}/{len(doc_files)} files successfully converted",
    )
    docx_files = [item.name for item in output_dir.iterdir() if item.suffix == ".docx"]
    docx_names = [item.split(".")[0] for item in docx_files]
    docx_paths = [str(output_dir / item) for item in docx_files]

    return dict(zip(docx_names, docx_paths, strict=False))


async def upload_file_to_gcp_and_create_payload(context: TurnContext, file_path: str) -> dict[str, str]:
    """Upload file to GCP bucket and create payload with file information using GCPHelper.

    Args:
        context: Context of the request
        file_path: Local path to the file to upload

    Returns:
        dict: Payload containing file information and GCP path

    """
    gcp_bucket_name = env.get_str("GCP_BUCKET_NAME", "ifdcpb-rag-store")

    try:
        # Get user info from context
        if context and context.activity and context.activity.from_property:
            user_id = context.activity.from_property.aad_object_id
        else:
            user_id = "unknown_user"

        if context and context.activity and context.activity.value and "user_choice" in context.activity.value:
            user_choice = loads(context.activity.value["user_choice"])
            collection_name = user_choice.get("name", "default_collection")
        else:
            collection_name = "default_collection"

        # Initialize GCP helper
        gcp_bucket = gcp_bucket_service
        # Upload file to GCP
        file_path_obj = Path(file_path)
        file_name = file_path_obj.name
        destination_path = f"docs_temp_folder/{user_id}/{collection_name}/{file_name}"
        await gcp_bucket.upload_file_to_gcp_bucket_async(str(file_path_obj), destination_path)
        gcp_url = f"https://storage.cloud.google.com/{gcp_bucket_name}/{destination_path}"
        # Create payload with file information
        payload = {
            "gcp_path": gcp_url,
            "gcp_full_path": destination_path,
            "file_name": file_name,
            "user_id": user_id,
            "collection_name": collection_name,
        }

        _logger.info(f"Successfully uploaded file to {gcp_url}")
        return payload

    except Exception as e:
        _logger.error(f"Error uploading file to GCP: {e!s}")
        raise


async def helper_convert_file_to_markdown_async(file_path: str) -> str:
    """Convert a file to Markdown using WebSocket (docling-serve async + status pub/sub)."""
    start_time = time.time()
    try:
        success, result = await convert_file_via_docling_websocket_subscription(file_path)
        if not success:
            # Convert failure to DoclingException for backward compatibility
            raise DoclingException(result)
        doc = result
    except Exception as e:
        # Handle other conversion errors
        raise DoclingException(str(e)) from e

    end_time = time.time() - start_time
    _logger.info(f"Document {file_path} converted in {end_time:.2f} seconds using WebSocket.")
    return doc
