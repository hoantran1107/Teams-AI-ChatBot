"""Background notification module for file processing.

This module contains utility functions to send notifications to users about background processing
status of their uploaded files.
"""

import logging

from botbuilder.core import MessageFactory, TurnContext
from botbuilder.schema import Attachment

from src.adaptive_cards.card_utils import send_adaptive_card
from src.adaptive_cards.function_cards import (
    create_processing_complete_card,
    create_processing_error_card,
    create_processing_start_card,
    create_stage_one_completion_card,
)
from src.constants.app_constants import AdaptiveCardConst

_logger = logging.getLogger(__name__)

# Storage for processing notification activity IDs by conversation ID
_processing_notification_ids: dict[str, str] = {}


async def send_background_processing_start_notification(
    context: TurnContext,
    file_count: int,
) -> None:
    """Send a notification that background processing has started.

    Args:
        context: The turn context for the conversation
        collection_name: The name of the collection
        file_count: Number of files being processed

    Returns:
        None

    """
    card = create_processing_start_card(file_count)
    attachment = Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card)
    response = await context.send_activity(MessageFactory.attachment(attachment))

    # Store the activity ID for later update
    if response and hasattr(response, "id"):
        conversation_id = None
        if (
            context.activity
            and hasattr(context.activity, "conversation")
            and context.activity.conversation
            and hasattr(context.activity.conversation, "id")
        ):
            conversation_id = context.activity.conversation.id

        if conversation_id:
            _processing_notification_ids[conversation_id] = response.id
            _logger.info(
                "Stored processing notification ID %s for conversation %s",
                response.id,
                conversation_id,
            )


async def send_background_processing_complete_notification(
    context: TurnContext,
    collection_name: str,
    converted_file_names: list[str],
    unconverted_files_names: list[str],
) -> None:
    """Send a notification that background processing has completed successfully.

    Returns:
        None

    """
    card = create_processing_complete_card(collection_name, converted_file_names, unconverted_files_names)
    await send_adaptive_card(context, card)


async def send_background_processing_error_notification(
    context: TurnContext,
    collection_name: str,
    error_message: str,
    failed_files: list[str] | None = None,
) -> None:
    """Send a notification that background processing encountered an error.

    Args:
        context: The turn context for the conversation
        collection_name: The name of the collection
        error_message: The error message to display
        failed_files: Optional list of files that failed processing

    """
    card = create_processing_error_card(collection_name, error_message, failed_files)
    await send_adaptive_card(context, card)


async def send_stage_one_completion_notification(
    context: TurnContext,
    collection_name: str,
    file_count: int,
    success_count: int,
    failed_files: list[str] | None = None,
) -> None:
    """Send a notification that stage 1 (file storage) has completed.

    Args:
        context: The turn context for the conversation
        collection_name: The name of the collection
        file_count: Total number of files uploaded
        success_count: Number of files successfully stored
        failed_files: Optional list of files that failed storage

    """
    card = create_stage_one_completion_card(collection_name, file_count, success_count, failed_files)
    await send_adaptive_card(context, card)
