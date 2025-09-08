import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aiofiles
import aiohttp
from botbuilder.core import TurnContext
from fastapi import HTTPException

from src.cloud_runs.document_handler.docs_handler import start_up_file_to_gcp_bucket
from src.constants.docling_constant import DoclingConstant, DoclingException
from src.utils.file_helper import (
    helper_convert_file_to_markdown_async,
    upload_file_to_gcp_and_create_payload,
)

logging.getLogger("pdfminer").setLevel(logging.ERROR)

_logger = logging.getLogger(__name__)
MAX_FILES_CONVERT = 10


def is_supported_file(file_path: str) -> bool:
    """Check if the file type is supported.

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file type is supported, False otherwise

    """
    file_ext = Path(file_path).suffix.lower()
    return file_ext in DoclingConstant.SUPPORTED_FILES


async def _process_single_file(
    context: TurnContext,
    file_path: str,
    output_dir: str | None,
) -> tuple[str | None, str | None]:
    """Process a single file conversion.

    Returns:
        Tuple of (gcp_url, error_message). One will be None.

    """
    filename = Path(file_path).name
    try:
        message = await upload_file_to_gcp_and_create_payload(context, file_path)

        _logger.info("Starting conversion for %s", file_path)
        result = await helper_convert_file_to_markdown_async(file_path)
        _logger.info("Conversion completed for %s", file_path)

        # Create output Markdown file name
        file_path_obj = Path(file_path)
        actual_output_dir = output_dir if output_dir else str(file_path_obj.parent)
        Path(actual_output_dir).mkdir(parents=True, exist_ok=True)
        markdown_filename = file_path_obj.stem + ".md"
        markdown_path = str(Path(actual_output_dir) / markdown_filename)

        # Write Markdown content to file
        async with aiofiles.open(markdown_path, "w", encoding="utf-8") as f:
            await f.write(result)

        # Upload the Markdown file to GCP bucket
        _logger.info("Starting GCP upload for %s", markdown_filename)
        gcp_url = await asyncio.get_running_loop().run_in_executor(
            ThreadPoolExecutor(max_workers=1),
            start_up_file_to_gcp_bucket,
            markdown_filename,
            markdown_path,
            str(message.get("user_id")),
            str(message.get("collection_name")),
        )
        _logger.info("GCP upload completed for %s", markdown_filename)
        return gcp_url, None

    except DoclingException as e:
        error_msg = f"Docling conversion failed for '{filename}': {e!s}"
        _logger.error(error_msg)
        return None, f"'{filename}' (conversion failed)"
    except aiohttp.ServerTimeoutError:
        error_msg = f"Timeout while processing '{filename}'"
        _logger.error(error_msg)
        return None, f"'{filename}' (processing timeout)"
    except Exception as e:
        error_msg = f"Failed to process '{filename}': {e!s}"
        _logger.error(error_msg)
        return None, f"'{filename}' (processing failed)"


async def convert_all_files_local(
    context: TurnContext,
    file_path_list: list[str],
    output_dir: str | None = None,
) -> list[str]:
    """Convert all files to Markdown locally using multiple threads.

    Args:
        context: The TurnContext for the current conversation
        file_path_list: List of file paths to convert
        output_dir: Output directory for the MD files (if None, will use the same directory as each file)

    Returns:
        List of paths to the created Markdown files

    """
    # Check if the number of files exceeds the maximum
    if len(file_path_list) > MAX_FILES_CONVERT:
        msg = f"Too many files to convert. Maximum is {MAX_FILES_CONVERT}, but {len(file_path_list)} were provided."
        _logger.error(msg)
        raise HTTPException(
            status_code=413,  # Payload Too Large
            detail=msg,
        )

    # Check if all files are supported
    for file_path in file_path_list:
        if not is_supported_file(file_path):
            filename = Path(file_path).name
            file_ext = Path(file_path).suffix
            supported_formats = ", ".join(DoclingConstant.SUPPORTED_FILES)
            msg = f"File '{filename}' has unsupported type '{file_ext}'. Supported formats: {supported_formats}"
            _logger.error(msg)
            raise HTTPException(
                status_code=415,  # Unsupported Media Type
                detail=msg,
            )

    # Ensure output directory exists if specified
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Process all files
    start_time = time.time()
    converted_files = []
    failed_files = []

    for file_path in file_path_list:
        gcp_url, error_msg = await _process_single_file(context, file_path, output_dir)
        if gcp_url:
            converted_files.append(gcp_url)
        else:
            failed_files.append(error_msg)

    # Calculate conversion time
    total_time = time.time() - start_time

    # Display summary information
    _logger.info("\n=== CONVERSION RESULTS ===")
    _logger.info("Total files: %d", len(file_path_list))
    _logger.info("Total conversion time: %.2f seconds", total_time)
    _logger.info("Average time per file: %.2f seconds/file", total_time / len(file_path_list))

    # Log failed files for debugging
    if failed_files:
        error_details = "; ".join(failed_files)
        _logger.warning("Failed files: %s", error_details)

    if not converted_files:
        error_details = "; ".join(failed_files)
        if len(file_path_list) == 1:
            raise HTTPException(status_code=400, detail=error_details)
        raise HTTPException(status_code=400, detail=f"All files failed: {error_details}")

    return converted_files


async def convert_folder_to_markdown(
    context: TurnContext,
    folder_path: str,
    output_dir: str | None = None,
) -> list[str]:
    """Convert all supported files in a folder to Markdown.

    Args:
        context: The TurnContext for the current conversation
        folder_path: Path to the folder containing files to convert
        output_dir: Output directory for the MD files (if None, will use the same directory as each file)

    Returns:
        List of paths to the created Markdown files

    """
    folder_path_obj = Path(folder_path)
    if not folder_path_obj.is_dir():
        msg = f"Folder not found: {folder_path}"
        _logger.error(msg)
        raise HTTPException(
            status_code=404,  # Not Found
            detail=msg,
        )

    # Get all files in the folder and store their paths in a list
    file_path_list = [str(file_path) for file_path in folder_path_obj.iterdir() if file_path.is_file()]

    # Convert all files to Markdown
    res = await convert_all_files_local(context, file_path_list, output_dir)
    return res
