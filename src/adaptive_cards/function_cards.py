from pathlib import Path

import jsonpickle
from botbuilder.core import MessageFactory, TurnContext
from botbuilder.schema import Attachment

from src.adaptive_cards.card_utils import create_action, create_basic_card, create_error_card, send_adaptive_card
from src.config.settings import atlassian_jira_url
from src.constants.app_constants import AdaptiveCardConst
from src.constants.docling_constant import DoclingConstant
from src.services.jira_services.services.get_data import (
    get_all_sprint_in_board,
)

FULL_PERCENTAGE = 100


async def initial_progress_card(context: TurnContext) -> str:
    """Create and send an initial progress card."""
    initial_card = {
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_3,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Starting file upload...",
                "weight": "bolder",
            },
            {
                "type": AdaptiveCardConst.COLUMN_SET,
                "columns": [
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "0",
                        "items": [
                            {
                                "type": AdaptiveCardConst.CONTAINER,
                                "style": "accent",
                                "items": [{"type": AdaptiveCardConst.TEXT_BLOCK, "text": " "}],
                            },
                        ],
                    },
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "100",
                        "items": [{"type": AdaptiveCardConst.TEXT_BLOCK, "text": " "}],
                    },
                ],
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Preparing to process your files...",
                "wrap": True,
            },
        ],
    }
    initial_response = await context.send_activity(
        MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=initial_card)),
    )

    activity_id = initial_response.id if initial_response else None
    if not activity_id:
        msg = "Cannot get activity ID from initial progress card."
        raise ValueError(msg)

    return activity_id


async def check_and_send_unsupported_card(context: TurnContext, check_files: list) -> bool:
    """Send a custom error notification with icon, title and subtitle.

    Args:
        context: Turn context
        check_files: List of files to check

    """
    for file in check_files:
        file_name = file.name
        file_extension = Path(file_name).suffix
        if file_extension not in DoclingConstant.SUPPORTED_FILES:
            card_body = [
                {
                    "type": AdaptiveCardConst.COLUMN_SET,
                    "columns": [
                        {
                            "type": AdaptiveCardConst.COLUMN,
                            "width": "auto",
                            "items": [
                                {
                                    "type": AdaptiveCardConst.TEXT_BLOCK,
                                    "text": "⚠️",
                                    "size": "large",
                                    "color": "warning",
                                },
                            ],
                            "verticalContentAlignment": "Center",
                        },
                        {
                            "type": AdaptiveCardConst.COLUMN,
                            "width": "stretch",
                            "items": [
                                {
                                    "type": AdaptiveCardConst.TEXT_BLOCK,
                                    "text": "Unsupported file type",
                                    "weight": "bolder",
                                    "size": "medium",
                                    "color": "warning",
                                },
                            ],
                            "verticalContentAlignment": "Center",
                        },
                    ],
                },
                {
                    "type": AdaptiveCardConst.TEXT_BLOCK,
                    "text": (
                        f"Unsupported file type: {file_extension}. "
                        f"Supported types are: **{', '.join(DoclingConstant.SUPPORTED_FILES)}**"
                    ),
                    "wrap": True,
                    "spacing": "Small",
                },
            ]
            card = create_basic_card(
                title="",
                body_items=card_body,
                version=AdaptiveCardConst.CARD_VERSION_1_3,
            )
            await send_adaptive_card(context, card)
            return False

    return True


async def update_progress_card(
    context: TurnContext,
    activity_id: str,
    percentage: int,
    message: str,
    files: list | None = None,
) -> None:
    """Update the progress card with the current processing status."""
    body = [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": f"Processing: {percentage}% complete",
            "weight": "bolder",
        },
        {
            "type": AdaptiveCardConst.COLUMN_SET,
            "columns": [
                {
                    "type": AdaptiveCardConst.COLUMN,
                    "width": str(percentage),
                    "items": [
                        {
                            "type": AdaptiveCardConst.CONTAINER,
                            "style": "accent",
                            "items": [{"type": AdaptiveCardConst.TEXT_BLOCK, "text": " "}],
                        },
                    ],
                },
                {
                    "type": AdaptiveCardConst.COLUMN,
                    "width": str(FULL_PERCENTAGE - percentage),
                    "items": [{"type": AdaptiveCardConst.TEXT_BLOCK, "text": " "}],
                },
            ],
        },
        {"type": AdaptiveCardConst.TEXT_BLOCK, "text": message, "wrap": True},
    ]

    # If the percentage is 100% and files are provided, add each file as a separate line
    if percentage == FULL_PERCENTAGE and files and len(files) > 0:
        # Add a container for the file list
        file_container: dict = {
            "type": AdaptiveCardConst.CONTAINER,
            "style": "emphasis",
            "spacing": "medium",
            "items": [
                {
                    "type": AdaptiveCardConst.TEXT_BLOCK,
                    "text": "Files uploaded:",
                    "weight": "bolder",
                },
            ],
        }

        # Add each file as a separate line with a bullet point
        for file in files:
            file_container["items"].append(
                {
                    "type": AdaptiveCardConst.TEXT_BLOCK,
                    "text": f"- {file}",
                    "wrap": True,
                },
            )

        # Add the file list to the card body
        body.append(file_container)

    card = create_basic_card(
        title="",
        body_items=body,
        version=AdaptiveCardConst.CARD_VERSION_1_3,
    )

    activity = MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card))
    activity.id = activity_id
    await context.update_activity(activity)


def choose_collection_card(uploaded_files: list, user_choices: list) -> dict:
    """Create a collection card for user to choose where to save files."""
    return {
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_5,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Please select a collection to save your files",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": AdaptiveCardConst.CONTAINER,
                "style": "emphasis",
                "items": [
                    {
                        "type": AdaptiveCardConst.TEXT_BLOCK,
                        "text": "My Collections",
                        "weight": "Bolder",
                        "size": "Medium",
                    },
                    {
                        "type": AdaptiveCardConst.INPUT_CHOICE_SET,
                        "id": "user_choice",
                        "style": "expanded",
                        "isMultiSelect": False,
                        "choices": user_choices,
                        "placeholder": "Select one of your collections",
                        "isRequired": True,
                        "description": "Select one of your collections",
                    },
                ],
                "isVisible": len(user_choices) > 0,
            },
        ],
        "actions": [
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "Save",
                "data": {"action": "save_folder", "uploaded_files": uploaded_files},
            },
        ],
    }


# Adaptive card Jira
async def create_input_list_sprints_card(board_id: int, board_name: str = "") -> dict:
    """Create Adaptive card input list sprints for action."""
    sprints = await get_all_sprint_in_board(board_id)
    if not sprints:
        return create_error_card(
            title="No Sprints Found",
            message=f"⚠️ No sprints exist for {board_name}.",
        )
    return {
        AdaptiveCardConst.SCHEMA_ATTRIBUTE: AdaptiveCardConst.SCHEMA,
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_3,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": f"Sprint list for {board_name} board",
                "weight": "bolder",
                "size": "medium",
                "wrap": True,
            },
            {
                "type": AdaptiveCardConst.INPUT_CHOICE_SET,
                "id": "selected_sprint",
                "label": "Select Sprint",
                "isRequired": True,
                "errorMessage": "Please select a sprint",
                "isSearchable": True,
                "choices": [
                    {
                        "title": sprint.get("name", ""),
                        "value": jsonpickle.encode({"id": sprint_id, "name": sprint.get("name", "")}),
                    }
                    for sprint_id, sprint in sprints.items()
                ],
            },
            {
                "type": AdaptiveCardConst.INPUT_TEXT,
                "id": "confluence_page_id",
                "placeholder": "Confluence page ID (e.g., 123456)",
                "label": "Confluence Page ID (this page will be overwritten)",
                "isRequired": True,
                "errorMessage": "Confluence page ID must be a number",
                "regex": "^[0-9]+$",
            },
        ],
        "actions": [
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "Submit",
                "data": {"action": "submit_sprint_data", "board_name": board_name, "board_id": board_id},
            },
        ],
    }


def create_input_document_sprint_card(projects: dict | None = None) -> dict:
    """Create Adaptive card input for action."""
    # Initialize base card structure with project selection
    if projects is None:
        projects = {}
    return {
        AdaptiveCardConst.SCHEMA_ATTRIBUTE: AdaptiveCardConst.SCHEMA,
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_3,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "📝 Document Sprint",
                "weight": "bolder",
                "size": "medium",
                "wrap": True,
            },
            {
                "type": AdaptiveCardConst.INPUT_CHOICE_SET,
                "id": "selected_board",
                "label": "Project Name",
                "isRequired": True,
                "errorMessage": "Please select a project name",
                "isSearchable": True,
                "choices": [
                    {
                        "title": p.get("name", ""),
                        "value": jsonpickle.encode({"id": idx, "name": p.get("name", "")}),
                    }
                    for idx, p in sorted(projects.items(), key=lambda x: x[1].get("name", ""))
                ],
                "value": "",
            },
        ],
        "actions": [
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "List Sprint",
                "data": {
                    "action": "update_sprint_list",
                },
            },
        ],
    }


def create_input_card_sentiment(ticket_id: str) -> dict:
    """Create an adaptive card for user input."""
    return {
        "type": "AdaptiveCard",
        AdaptiveCardConst.SCHEMA_ATTRIBUTE: AdaptiveCardConst.SCHEMA,
        "version": AdaptiveCardConst.CARD_VERSION_1_5,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Draft Response",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": f"Ticket ID: {ticket_id}",
                "spacing": "Small",
            },
            {
                "type": AdaptiveCardConst.INPUT_TEXT,
                "id": "draft_message",
                "placeholder": "Enter your draft response here...",
                "isMultiline": True,
                "isRequired": True,
                "errorMessage": "Please enter your draft response",
            },
        ],
        "actions": [
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "Submit",
                "data": {
                    "ticket_key": ticket_id,
                    "action": "submit_draft",
                },
            },
        ],
    }


def create_board_card(page_boards: list, start: int, project_id: int, project_key: str) -> list:
    """Create items for adaptive Card."""
    board_list_items = []
    for idx, board in enumerate(page_boards, 1):
        board_name = board.get("name") or ""
        action_list_sprint = create_action(
            action_type=AdaptiveCardConst.ACTION_SUBMIT,
            title="List Sprints",
            data={
                "action": "list_sprints",
                "board_id": board.get("id") or "",
                "board_name": board.get("name") or "",
                "project_id": project_id,
                "project_key": project_key,
            },
        )
        board_list_items.append(
            {
                "type": AdaptiveCardConst.COLUMN_SET,
                "columns": [
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "stretch",
                        "items": [
                            {
                                "type": AdaptiveCardConst.TEXT_BLOCK,
                                "text": f"{start + idx}. {board_name}",
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
                                    action_list_sprint,
                                ],
                            },
                        ],
                    },
                ],
                "spacing": "Small",
            },
        )
    return board_list_items


def create_project_card(page_projects: dict, start: int) -> list:
    """Create items for adaptive Card."""
    project_list_items = []
    for idx, (pid, pro) in enumerate(page_projects, 1):
        project_name = pro.get("name") or ""
        project_key = pro.get("project_key") or ""
        action_list_boards = create_action(
            action_type=AdaptiveCardConst.ACTION_SUBMIT,
            title="List Boards",
            data={
                "action": "list_boards",
                "project_id": pid,
                "project_name": project_name,
                "project_key": project_key,
            },
        )
        project_list_items.append(
            {
                "type": AdaptiveCardConst.COLUMN_SET,
                "columns": [
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "stretch",
                        "items": [
                            {
                                "type": AdaptiveCardConst.TEXT_BLOCK,
                                "text": f"{start + idx}. {project_name}",
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
                                    action_list_boards,
                                ],
                            },
                        ],
                    },
                ],
                "spacing": "Small",
            },
        )
    return project_list_items


def create_sprint_items(page_sprints: list, start: int, board_id: int, board_name: str, project_key: str) -> list:
    """Create Sprint items for adaptive card."""
    sprint_items = []
    for idx, (sprint_id, sprint_data) in enumerate(page_sprints, 1):
        sprint_name = sprint_data.get("name") or ""
        sprint_state = sprint_data.get("state") or ""
        action_list_tickets = create_action(
            action_type=AdaptiveCardConst.ACTION_SUBMIT,
            title="List Tickets",
            data={
                "action": "list_tickets",
                "board_id": board_id,
                "board_name": board_name,
                "project_key": project_key,
                "sprint_id": sprint_id,
                "sprint_name": sprint_name,
            },
        )
        action_summary_sprint = create_action(
            action_type=AdaptiveCardConst.ACTION_SUBMIT,
            title="Summary Sprint",
            data={
                "action": "summary_sprint",
                "board_id": board_id,
                "board_name": board_name,
                "project_key": project_key,
                "sprint_id": sprint_id,
                "sprint_data": sprint_data,
            },
        )
        sprint_items.append(
            {
                "type": AdaptiveCardConst.CONTAINER,
                "items": [
                    {
                        "type": AdaptiveCardConst.COLUMN_SET,
                        "spacing": "Small",
                        "columns": [
                            {
                                "type": AdaptiveCardConst.COLUMN,
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": AdaptiveCardConst.TEXT_BLOCK,
                                        "text": f"{start + idx}. {sprint_name} ({sprint_state})",
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
                                        "horizontalAlignment": "right",
                                        "actions": [
                                            action_list_tickets,
                                            action_summary_sprint,
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                ],
                "separator": True,
                "spacing": "Medium",
            },
        )
    return sprint_items


def create_ticket_items(page_tickets: dict, start: int) -> list:
    """Create Ticket items for adaptive card."""
    ticket_blocks = []
    for idx, (key, ticket) in enumerate(page_tickets, 1):
        action_view_ticket = create_action(
            action_type=AdaptiveCardConst.ACTION_OPEN_URL,
            title="View Ticket",
            url=f"{atlassian_jira_url}/browse/{key}",
        )
        action_get_ticket = create_action(
            action_type=AdaptiveCardConst.ACTION_SUBMIT,
            title="Get Information of a Jira Ticket",
            data={
                "action": "get_jira_ticket_info",
                "tickets": [key],
            },
        )
        item_text = (
            f"**{start + idx}. [{key}]**\n"
            f"• Assignee: {ticket.get('Assignee') or 'Unassigned'}\n"
            f"• Status: {ticket.get('Status') or 'Unknown'}\n"
        )
        ticket_blocks.append(
            {
                "type": AdaptiveCardConst.CONTAINER,
                "items": [
                    {
                        "type": AdaptiveCardConst.TEXT_BLOCK,
                        "text": item_text,
                        "wrap": True,
                        "spacing": "Medium",
                    },
                    {
                        "type": AdaptiveCardConst.ACTION_SET,
                        "actions": [
                            action_view_ticket,
                            action_get_ticket,
                        ],
                    },
                ],
                "separator": True,
                "spacing": "Medium",
            },
        )
    return ticket_blocks


def create_processing_start_card(file_count: int) -> dict:
    """Create an adaptive card for the start of document processing.

    Args:
        file_count: Number of files being processed

    Returns:
        Adaptive card as a dictionary

    """
    return {
        "type": "AdaptiveCard",
        "version": "1.3",
        "body": [
            {
                "type": "TextBlock",
                "text": "⏳ Processing Documents",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": "🔄",
                                        "size": "Medium",
                                    },
                                ],
                            },
                            {
                                "type": "Column",
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": f"Processing {file_count} file(s)...",
                                        "wrap": True,
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "type": "TextBlock",
                "text": ("Processing your file(s). This may take a few moments."),
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": "TextBlock",
                "text": "You can continue chatting while I work on this.",
                "wrap": True,
                "spacing": "Small",
                "isSubtle": True,
            },
        ],
    }


def create_processing_complete_card(
    collection_name: str,
    converted_file_names: list[str],
    unconverted_files_names: list[str],
) -> dict:
    """Create an adaptive card for successful document processing completion.

    Args:
        collection_name: The name of the collection
        converted_file_names: List of successfully processed file names
        unconverted_files_names: List of files that failed processing

    Returns:
        Adaptive card as a dictionary

    """
    num_converted = len(converted_file_names)

    # Process text content before card construction
    status_text = f"{num_converted} file(s) have been processed."
    processed_files_text = (
        "List of processed files:\n- " + "\n- ".join(converted_file_names)
        if converted_file_names
        else "List of processed files: None."
    )
    unprocessed_files_text = (
        "List of unprocessed files (if any):\n- " + "\n- ".join(unconverted_files_names)
        if unconverted_files_names
        else "List of unprocessed files: None."
    )

    return {
        "type": "AdaptiveCard",
        "version": "1.3",
        "body": [
            {
                "type": "TextBlock",
                "text": "✅ Documents Ready",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Good",
            },
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": "📚",
                                        "size": "Medium",
                                    },
                                ],
                            },
                            {
                                "type": "Column",
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": status_text,
                                        "wrap": True,
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "type": "TextBlock",
                "text": processed_files_text,
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": "TextBlock",
                "text": unprocessed_files_text,
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": "TextBlock",
                "text": f"Try asking questions about your documents in collection **{collection_name}**",
                "wrap": True,
                "spacing": "Medium",
            },
        ],
    }


def create_processing_error_card(
    collection_name: str,
    error_message: str,
    failed_files: list[str] | None = None,
) -> dict:
    """Create an adaptive card for document processing errors.

    Args:
        collection_name: The name of the collection
        error_message: The error message to display
        failed_files: Optional list of files that failed processing

    Returns:
        Adaptive card as a dictionary

    """
    body = [
        {
            "type": "TextBlock",
            "text": "⚠️ Processing Issue",
            "weight": "Bolder",
            "size": "Medium",
            "color": "Warning",
        },
        {
            "type": "Container",
            "style": "attention",
            "spacing": "medium",
            "items": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "⚠️",
                                    "size": "Medium",
                                },
                            ],
                        },
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": error_message,
                                    "wrap": True,
                                },
                            ],
                        },
                    ],
                },
            ],
        },
        {
            "type": "TextBlock",
            "text": (
                f"Your documents were stored in collection **{collection_name}**, but "
                f"I encountered an issue while processing them for search."
            ),
            "wrap": True,
            "spacing": "Medium",
        },
    ]

    # If there are specific failed files, list them
    if failed_files:
        file_container: dict = {
            "type": "Container",
            "style": "emphasis",
            "spacing": "medium",
            "items": [
                {
                    "type": "TextBlock",
                    "text": "Files with issues:",
                    "weight": "bolder",
                },
            ],
        }

        for file in failed_files:
            file_container["items"].append(
                {
                    "type": "TextBlock",
                    "text": f"- {file}",
                    "wrap": True,
                },
            )

        body.append(file_container)

    # Add a note about being able to chat
    body.append(
        {
            "type": "TextBlock",
            "text": "You can continue chatting with me about other topics.",
            "wrap": True,
            "spacing": "Medium",
        },
    )

    return {
        "type": "AdaptiveCard",
        "version": "1.3",
        "body": body,
    }


def create_stage_one_completion_card(
    collection_name: str,
    file_count: int,
    success_count: int,
    failed_files: list[str] | None = None,
) -> dict:
    """Create an adaptive card for stage one (file storage) completion.

    Args:
        collection_name: The name of the collection
        file_count: Total number of files uploaded
        success_count: Number of files successfully stored
        failed_files: Optional list of files that failed storage

    Returns:
        Adaptive card as a dictionary

    """
    # Different message based on full or partial success
    if success_count == file_count:
        title = "✅ Upload Complete"
        color = "Good"
        main_message = f"Uploaded your {file_count} file(s) to collection **{collection_name}**."
    else:
        title = "⚠️ Upload Partially Complete"
        color = "Warning"
        main_message = f"Uploaded {success_count} of {file_count} file(s) to collection **{collection_name}**."

    body = [
        {
            "type": "TextBlock",
            "text": title,
            "weight": "Bolder",
            "size": "Medium",
            "color": color,
        },
        {
            "type": "TextBlock",
            "text": main_message,
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": "You can continue chatting while I process your files for use.",
            "wrap": True,
            "spacing": "Small",
        },
    ]

    # If there are specific failed files, list them
    if failed_files:
        file_container: dict = {
            "type": "Container",
            "style": "emphasis",
            "spacing": "medium",
            "items": [
                {
                    "type": "TextBlock",
                    "text": "Files with issues:",
                    "weight": "bolder",
                },
            ],
        }

        for file in failed_files:
            file_container["items"].append(
                {
                    "type": "TextBlock",
                    "text": f"- {file}",
                    "wrap": True,
                },
            )

        body.append(file_container)

    return {
        "type": "AdaptiveCard",
        "version": "1.3",
        "body": body,
    }
