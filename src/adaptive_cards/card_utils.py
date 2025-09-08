"""Adaptive Card Utilities and Common Components.

This module provides utility functions, constants, and reusable components
for creating consistent adaptive cards throughout the application.
"""

import logging
import math

from botbuilder.core import MessageFactory, TurnContext
from botbuilder.schema import Activity, Attachment

from src.bots.data_model.app_state import AppTurnState
from src.bots.data_model.history_adaptive_card import save_history
from src.constants.app_constants import AdaptiveCardConst

_logger = logging.getLogger(__name__)


def create_basic_card(
    title: str,
    body_items: list | None = None,
    actions: list | None = None,
    version: str = AdaptiveCardConst.CARD_VERSION_1_3,
) -> dict:
    """Create a basic adaptive card with title and optional body items and actions.

    Args:
        title (str): The card title
        body_items (list): Optional list of body items
        actions (list): Optional list of action objects
        version (str): Card schema version

    Returns:
        dict: An adaptive card object

    """
    card: dict = {
        "type": "AdaptiveCard",
        "version": version,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": title,
                "weight": "Bolder",
                "size": "Medium",
            },
        ],
    }

    # Add body items if provided
    if body_items:
        card["body"].extend(body_items)

    # Add actions if provided
    if actions:
        card["actions"] = actions

    # Add schema reference
    card[AdaptiveCardConst.SCHEMA_ATTRIBUTE] = AdaptiveCardConst.SCHEMA

    return card


def create_text_block(
    text: str,
    weight: str | None = None,
    size: str | None = None,
    color: str | None = None,
    is_subtle: bool = False,
    wrap: bool = True,
) -> dict:
    """Create a text block with common formatting options.

    Args:
        text (str): The text content
        weight (str): Optional text weight ("Default", "Lighter", "Bolder")
        size (str): Optional text size ("Small", "Default", "Medium", "Large", "ExtraLarge")
        color (str): Optional text color ("Default", "Accent", "Good", "Warning", "Attention")
        is_subtle (bool): Whether the text should be subtle
        wrap (bool): Whether the text should wrap

    Returns:
        dict: A text block object

    """
    text_block = {"type": AdaptiveCardConst.TEXT_BLOCK, "text": text, "wrap": wrap}

    if weight:
        text_block["weight"] = weight

    if size:
        text_block["size"] = size

    if color:
        text_block["color"] = color

    if is_subtle:
        text_block["isSubtle"] = is_subtle

    return text_block


def create_input(
    input_type: str,
    id_input: str,
    placeholder: str | None = None,
    value: str | None = None,
    is_required: bool = False,
    error_message: str | None = None,
) -> dict:
    """Create an input component with common options.

    Args:
        input_type (str): The type of input (e.g., "Input.Text", "Input.ChoiceSet")
        id_input (str): The input identifier
        placeholder (str): Optional placeholder text
        value: Optional default value
        is_required (bool): Whether the input is required
        error_message (str): Optional error message for validation

    Returns:
        dict: An input component object

    """
    input_component: dict = {"type": input_type, "id": id_input}

    if placeholder:
        input_component["placeholder"] = placeholder

    if value is not None:
        input_component["value"] = value

    if is_required:
        input_component["isRequired"] = is_required

    if error_message:
        input_component["errorMessage"] = error_message

    return input_component


def create_action(
    action_type: str,
    title: str,
    data: dict | None = None,
    url: str | None = None,
    style: str | None = None,
) -> dict:
    """Create an action for adaptive cards.

    Args:
        action_type (str): The type of action (e.g., "Action.Submit", "Action.OpenUrl")
        title (str): The button text
        data (dict): Optional data payload for the action
        url (str): Optional URL for OpenUrl actions
        style (str): Optional button style ("default", "positive", "destructive")

    Returns:
        dict: An action object

    """
    action: dict = {"type": action_type, "title": title}

    if data:
        action["data"] = data

    if url and action_type == AdaptiveCardConst.ACTION_OPEN_URL:
        action["url"] = url

    if style:
        action["style"] = style

    return action


def create_success_card(title: str, message: str, additional_items: list | None = None) -> dict:
    """Create a success message card.

    Args:
        title (str): The success title
        message (str): The success message
        additional_items (list): Optional additional body items

    Returns:
        dict: A success card object

    """
    body = [
        create_text_block(
            text=title,
            weight="Bolder",
            size="Medium",
            color=AdaptiveCardConst.COLOR_GOOD,
        ),
        create_text_block(message),
    ]

    if additional_items:
        body.extend(additional_items)

    return create_basic_card("", body_items=body)


def create_error_card(title: str, message: str, additional_items: list | None = None) -> dict:
    """Create an error message card.

    Args:
        title (str): The error title
        message (str): The error message
        additional_items (list): Optional additional body items

    Returns:
        dict: An error card object

    """
    body = [
        create_text_block(
            text=title,
            weight="Bolder",
            size="Medium",
            color=AdaptiveCardConst.COLOR_ATTENTION,
        ),
        create_text_block(message),
    ]

    if additional_items:
        body.extend(additional_items)

    return create_basic_card("", body_items=body)


def get_pagination_details(items: list, items_per_page: int, page: int) -> list:
    """Calculate pagination details for a list of items."""
    total_pages = max(1, math.ceil(len(items) / items_per_page))
    page = max(1, min(page, total_pages))
    start = (page - 1) * items_per_page
    end = start + items_per_page
    page_items = items[start:end]
    return [total_pages, page, start, end, page_items]


def create_page_info(start: int, end: int, items: list, page: int, total_pages: int) -> tuple:
    """Create page information and indicator for adaptive card."""
    page_info = f"Showing {start + 1}-{min(end, len(items))} of {len(items)} items"
    page_indicator = {
        "type": AdaptiveCardConst.TEXT_BLOCK,
        "text": f"Page {page} of {total_pages}",
        "horizontalAlignment": "Center",
        "weight": "Bolder",
        "color": AdaptiveCardConst.COLOR_ACCENT,
        "spacing": "Small",
    }
    return page_info, page_indicator


def build_card_body(
    title: str,
    page_info: str,
    page_indicator: dict,
    items: list | None = None,
    extra_elements: list | None = None,
) -> list:
    """Build the body of an adaptive card."""
    body = [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": title,
            "weight": "Bolder",
            "size": "Medium",
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": page_info,
            "spacing": "Small",
            "size": "Small",
            "isSubtle": True,
        },
        page_indicator,
    ]
    if extra_elements:
        for element in extra_elements:
            if element:
                body.insert(1, element)

    if items:
        body.append({"type": AdaptiveCardConst.CONTAINER, "items": items})
    return body


async def handle_activity(
    context: TurnContext,
    state: AppTurnState,
    action: str,
    target_action: str,
    activity: Activity,
    state_key: str,
    user_content: str = "",
    history_data: list | None = None,
) -> None:
    """Handle sending or updating an activity."""
    if action == target_action:
        response = await context.send_activity(activity)
        setattr(state.user, state_key, response.id)

        save_history(state, user_content, history_data)
    else:
        try:
            activity.id = getattr(state.user, state_key)
            await context.update_activity(activity)
        except Exception:
            response = await context.send_activity(activity)
            _logger.warning("Failed to update %s message, sending a new one instead.", state_key)
            setattr(state.user, state_key, response.id)


def build_paging_card(
    page: int,
    total_pages: int,
    action_prefix: str,
    extra_data: dict | None = None,
    include_last: bool = True,
) -> list:
    """Build card actions for pagination."""
    extra_data = extra_data or {}
    actions = [
        {
            "type": AdaptiveCardConst.ACTION_SUBMIT,
            "title": "Previous",
            "data": {"action": f"{action_prefix}_prev_page", "page": page - 1, **extra_data},
            "isEnabled": page > 1,
        },
        {
            "type": AdaptiveCardConst.ACTION_SUBMIT,
            "title": "Next",
            "data": {"action": f"{action_prefix}_next_page", "page": page + 1, **extra_data},
            "isEnabled": page < total_pages,
        },
    ]
    if include_last:
        actions.append(
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "Last",
                "data": {"action": f"{action_prefix}_last_page", "page": total_pages, **extra_data},
                "isEnabled": page < total_pages,
            },
        )

    return actions


async def send_adaptive_card(context: TurnContext, card: dict) -> None:
    """Send and Save data Adaptive card."""
    # Create attachment from card
    attachment = Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card)
    activity = MessageFactory.attachment(attachment)
    # Send new activity and store its ID
    await context.send_activity(activity)


def create_filter_info(filtered_count: int, total_count: int, search_text: str, clear_action: str, **kwargs) -> dict:
    """Create filter information display with clear button."""
    return {
        "type": AdaptiveCardConst.COLUMN_SET,
        "spacing": "Small",
        "columns": [
            {
                "type": AdaptiveCardConst.COLUMN,
                "width": "stretch",
                "items": [
                    {
                        "type": AdaptiveCardConst.TEXT_BLOCK,
                        "text": f"Filtered: {filtered_count} of {total_count} search match '{search_text}'",
                        "size": "Small",
                        "wrap": True,
                    },
                ],
            },
            {
                "type": AdaptiveCardConst.COLUMN,
                "width": "auto",
                "items": [
                    {
                        "type": AdaptiveCardConst.ACTION_SET,
                        "actions": [
                            {
                                "type": AdaptiveCardConst.ACTION_SUBMIT,
                                "title": "Clear",
                                "style": "destructive",
                                "data": {
                                    "action": clear_action,
                                    **kwargs,
                                },
                            },
                        ],
                    },
                ],
            },
        ],
    }
