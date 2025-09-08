import json
import logging
import tempfile
from http import HTTPStatus
from pathlib import Path

import aiofiles
import aiohttp
from botbuilder.core import TurnContext
from botbuilder.schema.teams.additional_properties import ContentType

from src.adaptive_cards.card_utils import send_adaptive_card
from src.adaptive_cards.function_cards import (
    choose_collection_card,
    initial_progress_card,
    update_progress_card,
)
from src.bots.data_model.app_state import AppTurnState
from src.bots.handlers.attachment.background_notification import (
    send_background_processing_complete_notification,
    send_background_processing_error_notification,
    send_background_processing_start_notification,
    send_stage_one_completion_notification,
)
from src.bots.handlers.attachment.convert_file_to_md import (
    convert_folder_to_markdown,
)
from src.config.environment import env
from src.constants.docling_constant import DoclingConstant
from src.enums.enum import ServiceResultEnum
from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service
from src.services.manage_rag_sources.services.manage_source import ManageSource

gcp_bucket_name = env.get_str("GCP_BUCKET_NAME", "ifdcpb-rag-store")
CARD_CONTENT_TYPE = "application/vnd.microsoft.card.adaptive"
TEMP_FILE_DIRECTORY = "files/"
DEFAULT_FILE_NAME = "teams-logo.png"

_logger = logging.getLogger(__name__)


async def download_attachments(activity_attachments: list[dict], directory: str) -> None:
    """Download attachments from the activity to a specified directory."""
    async with aiohttp.ClientSession() as session:
        for attachment in activity_attachments:
            if attachment["contentType"] == ContentType.FILE_DOWNLOAD_INFO and attachment["name"].endswith(
                tuple(DoclingConstant.SUPPORTED_FILES),
            ):
                file_path = Path(directory) / attachment["name"]
                # Download the file
                async with session.get(
                    attachment["content"].get("downloadUrl"),
                    allow_redirects=True,
                ) as response:
                    # Use Python's built-in HTTPStatus for proper success checking
                    if HTTPStatus(response.status).is_success:  # Checks 200-299 range
                        content = await response.read()
                        async with aiofiles.open(file_path, "wb") as f:
                            await f.write(content)
                    else:
                        _logger.error(
                            "Failed to download user file: %s",
                            response.status,
                        )


# Add validation for user state before proceeding
async def ask_for_choosing_collection(context: TurnContext, uploaded_files: list) -> None:
    """Send an adaptive card that asks the user to select a collection from existing collections.

    Args:
        context: The turn context
        uploaded_files: List of uploaded files

    """
    # Validate uploaded_files
    if not uploaded_files:
        await context.send_activity(
            "❌ No files were uploaded. Please upload a file before proceeding.",
        )
        return

    # Get user ID for user-specific sources
    user_id = context.activity.from_property.id if context.activity.from_property else None
    if not user_id:
        msg = "Error: ❌ Cannot determine user ID from activity."
        await context.send_activity(msg)
        _logger.error(msg)
        return

    # Get common and user-specific sources
    user_sources = ManageSource.get_source_name_by_user_id(user_id)

    # Check if user has any collections
    if not user_sources:
        await context.send_activity(
            "❌ You do not have any collections. Please create one before proceeding.",
        )
        return

    # Prepare user-specific collections choices
    user_choices = [
        {
            "title": source.name,
            "value": json.dumps({"name": source.name, "id": source.id}),
        }
        for source in user_sources
    ]

    # Create the adaptive card
    card = choose_collection_card(uploaded_files, user_choices)
    await send_adaptive_card(context, card)


def remove_extension_from_filename(filename: str) -> str:
    """Remove the file extension from the filename."""
    if filename:
        return Path(filename).with_suffix("").name
    return filename


async def handel_upload_files_to_gcp(context: TurnContext, _state: AppTurnState) -> None:
    """Handle uploading files to GCP bucket with progress tracking.

    This function has been updated to separate the file processing into two stages:
    1. Storage/preparation - downloads attachments and uploads to GCP bucket (fast)
    2. Conversion/ingestion - converts files to markdown and indexes them (slower background process)

    This separation allows users to continue chatting while processing happens in the background.

    Args:
        context: The turn context containing activity data
        state: Application turn state

    Returns:
        None

    """
    # Initial progress card with 0%
    activity_id = await initial_progress_card(context)

    # STAGE 1: FILE STORAGE AND PREPARATION (FAST)
    with tempfile.TemporaryDirectory() as folder_name:
        _user_id = context.activity.from_property.aad_object_id if context.activity.from_property else None
        uploaded_files = context.activity.value.get("uploaded_files") if context.activity.value else None
        user_choice = json.loads(context.activity.value.get("user_choice")) if context.activity.value else None
        if not _user_id or not uploaded_files or not user_choice:
            msg = "Error: ❌ Cannot find user ID, uploaded files, or collection choice."
            await update_progress_card(context, activity_id, 100, msg)
            _logger.error(msg)
            return

        collection_id = user_choice["id"]
        collection_name = user_choice["name"]

        # Download stage - 50%
        await update_progress_card(
            context,
            activity_id,
            50,
            "Downloading your files...",
        )
        await download_attachments(uploaded_files, folder_name)

        # Check for files
        folder_path = Path(folder_name)
        extracted_file_names = [f.name for f in folder_path.iterdir() if f.is_file()]
        extracted_file_names_without_ext = [remove_extension_from_filename(f) for f in extracted_file_names]
        file_and_link = {
            remove_extension_from_filename(f["name"]): {
                "onedrive": f["contentUrl"],
                "gcp": None,
            }
            for f in uploaded_files
        }
        if not extracted_file_names:
            await update_progress_card(
                context,
                activity_id,
                100,
                "❌ No files found in your temporary folder.",
            )
            return

        # STAGE 1 COMPLETION NOTIFICATION
        # Tell the user their files are being stored and they can continue chatting
        await update_progress_card(
            context,
            activity_id,
            100,
            "",  # No message needed here
        )
        await send_stage_one_completion_notification(
            context,
            collection_name=collection_name,
            file_count=len(uploaded_files),
            success_count=len(extracted_file_names),
        )

        # STAGE 2: CONVERSION AND INGESTION (SLOWER, BACKGROUND PROCESS)
        # Notify that background processing has started
        await send_background_processing_start_notification(
            context,
            file_count=len(extracted_file_names),
        )

        with tempfile.TemporaryDirectory() as converted_folder:
            # Convert files with try-catch
            try:
                converted_gcp_path_files = await convert_folder_to_markdown(
                    context,
                    folder_name,
                    converted_folder,
                )
            except Exception as e:  # noqa: BLE001
                error_msg = str(e)
                final_msg = (
                    "❌ File conversion failed: The file may be corrupted, password-protected,"
                    " or in an unsupported format."
                )
                _logger.error("File conversion error: %s", error_msg)
                await send_background_processing_error_notification(
                    context,
                    collection_name=collection_name,
                    error_message=final_msg,
                )
                return

            # Upload and database operations
            try:
                # Update file links
                for _url in converted_gcp_path_files:
                    file_name = Path(_url).name
                    file_and_link[remove_extension_from_filename(file_name)]["gcp"] = _url

                file_bucket_links = []
                public_view_urls = []
                for links in file_and_link.values():
                    if links["gcp"] is not None:
                        file_bucket_links.append(links["gcp"])
                        public_view_urls.append(links["onedrive"])

                result = await ManageSource.add_gcp_file(
                    collection_id=collection_id,
                    file_bucket_links=file_bucket_links,
                    public_view_urls=public_view_urls,
                    auto_run_cron_job=True,
                )

                if result.status != ServiceResultEnum.SUCCESS:
                    error_msg = f"❌ Error adding files to collection: {result.error}"
                    await send_background_processing_error_notification(
                        context,
                        collection_name=collection_name,
                        error_message=error_msg,
                    )
                    return

                # Prepare success notification
                converted_file_names: list[str] = [Path(f).stem for f in converted_gcp_path_files]
                unconverted_files_names: list[str] = list(
                    set(extracted_file_names_without_ext) - set(converted_file_names),
                )

                # Send background processing completion notification
                await send_background_processing_complete_notification(
                    context,
                    collection_name=collection_name,
                    converted_file_names=converted_file_names,
                    unconverted_files_names=unconverted_files_names,
                )

            except Exception as e:
                error_msg = f"❌ Error uploading files to GCP bucket: {e!s}"
                await send_background_processing_error_notification(
                    context,
                    collection_name=collection_name,
                    error_message=error_msg,
                )


def start_up_file_to_gcp_bucket(
    folder_name: str,
    user_id: str,
    collection_name: str,
    file_and_link: dict,
) -> dict:
    """Upload all files from a local directory to a GCP bucket.

    Args:
        folder_name: Path to the directory containing files to upload
        user_id: User ID (e.g., tien-test)
        collection_name: Collection name (e.g., collection1)
        file_and_link: Dictionary containing file links

    Returns:
        dict: Dictionary with updated URLs of uploaded files

    """
    # Initialize client
    storage_client = gcp_bucket_service.client

    # Reference to bucket
    bucket = storage_client.bucket(gcp_bucket_name)

    # Fixed path
    fixed_path = "files"

    # Check if the directory exists
    folder_path = Path(folder_name)
    if not folder_path.exists():
        error_msg = f"Directory '{folder_name}' does not exist"
        raise FileNotFoundError(error_msg)

    # Get all files in the directory
    files = [f.name for f in folder_path.iterdir() if f.is_file()]

    if not files:
        _logger.warning("No files found in directory '%s'", folder_name)
        return {}

    # Upload each file
    for file_name in files:
        local_file_path = folder_path / file_name

        # Destination path in the bucket
        destination_path = f"{fixed_path}/{user_id}/{collection_name}/{file_name}"

        # Create blob
        blob = bucket.blob(destination_path)

        # Upload file
        try:
            blob.upload_from_filename(local_file_path)
            _logger.info("File '%s' uploaded successfully", file_name)

            # Create URL without encoding filename as required
            url = f"https://storage.cloud.google.com/{gcp_bucket_name}/{destination_path}"
            file_and_link[remove_extension_from_filename(file_name)]["gcp"] = url

        except Exception as e:
            _logger.error("Error uploading file '%s': %s", file_name, e)

    return file_and_link
