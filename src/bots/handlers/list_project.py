from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ActivityTypes, Attachment

from src.adaptive_cards.card_utils import (
    build_card_body,
    build_paging_card,
    create_action,
    create_basic_card,
    create_filter_info,
    create_page_info,
    get_pagination_details,
    handle_activity,
)
from src.adaptive_cards.function_cards import create_board_card, create_project_card
from src.bots.data_model.app_state import AppTurnState
from src.constants.action_types import JiraActions
from src.constants.app_constants import AdaptiveCardConst, PagingConst
from src.services.jira_services.services.get_data import (
    fetch_fallback_projects,
    get_all_board_from_project,
)
from src.services.jira_services.services.jira_utils import extract_context_data


async def handle_list_boards(context: TurnContext, state: AppTurnState) -> None:
    """Handle Adaptive card action List boards."""
    action, _, page = get_action_data(context, "board")
    project_id, project_key = extract_context_data(context, ["project_id", "project_key"])

    boards = await get_all_board_from_project(str(project_id))
    total_pages, page, start, end, page_boards = get_pagination_details(boards, PagingConst.PAGING_SIZE, page)
    board_list_items = create_board_card(page_boards, start, project_id, project_key)
    page_info, page_indicator = create_page_info(start, end, page_boards, page, total_pages)

    if not page_boards:
        await context.send_activity(f"No scrum boards found for {project_key} project.")
        return

    card_body = build_card_body(
        title=f"**List of scrum boards for {project_key}**",
        page_info=page_info,
        page_indicator=page_indicator,
        items=board_list_items,
    )
    actions = build_paging_card(
        page,
        total_pages,
        JiraActions.LIST_BOARDS,
        {"project_id": project_id, "project_key": project_key},
        include_last=False,
    )

    card = create_basic_card(
        title="",
        body_items=card_body,
        actions=actions,
        version=AdaptiveCardConst.CARD_VERSION_1_4,
    )
    activity = Activity(
        type=ActivityTypes.message,
        attachments=[Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card)],
    )
    list_board = _saving_boards_field(boards)
    await handle_activity(
        context=context,
        state=state,
        action=action,
        target_action=JiraActions.LIST_BOARDS,
        activity=activity,
        state_key=JiraActions.STATE_BOARD,
        user_content="List all of Jira Boards",
        history_data=list_board,
    )


async def handle_list_projects(context: TurnContext, state: AppTurnState) -> None:
    """Handle Adaptive card action List projects."""
    action, search_query, page = get_action_data(context, "project")
    projects = await fetch_fallback_projects()
    filtered_projects = get_filtered_projects(projects, search_query)
    total_pages, page, start, end, page_projects = get_pagination_details(
        filtered_projects,
        PagingConst.PAGING_SIZE,
        page,
    )
    project_list_items = create_project_card(page_projects, start)
    page_info, page_indicator = create_page_info(start, end, filtered_projects, page, total_pages)
    extension = {"search": ""}
    filter_info = create_filter_info(
        len(filtered_projects),
        len(projects),
        search_query,
        "clear_project_search",
        **extension,
    )

    card_body = build_card_body(
        title="**List of Jira Projects**",
        page_info=page_info,
        page_indicator=page_indicator,
        items=project_list_items,
        extra_elements=[
            {
                "type": AdaptiveCardConst.INPUT_TEXT,
                "id": "search",
                "placeholder": "Search projects...",
                "value": search_query,
            },
            filter_info if filter_info else None,
        ],
    )
    actions = build_paging_card(
        page,
        total_pages,
        JiraActions.LIST_PROJECTS,
        {"search": search_query},
        include_last=False,
    )

    # Add search action to the beginning of the actions list
    action_search = create_action(
        action_type=AdaptiveCardConst.ACTION_SUBMIT,
        title="Search",
        data={"action": "search_projects", "search": "${search}"},
    )
    actions.insert(
        0,
        action_search,
    )

    card = create_basic_card(
        title="",
        body_items=card_body,
        actions=actions,
        version=AdaptiveCardConst.CARD_VERSION_1_4,
    )
    activity = Activity(
        type=ActivityTypes.message,
        attachments=[Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card)],
    )
    list_project = _saving_project_field(projects)
    await handle_activity(
        context=context,
        state=state,
        action=action,
        target_action=JiraActions.LIST_PROJECTS,
        activity=activity,
        state_key=JiraActions.STATE_PROJECT,
        user_content="List all of Jira Projects",
        history_data=list_project,
    )


def get_action_data(context: TurnContext, type_action: str) -> list:
    """Get action from adaptive card."""
    action_data = context.activity.value or {}
    action = (
        action_data.get("action", "search_projects")
        if type_action == "project"
        else action_data.get("action", "search_boards")
    )
    search_query = action_data.get("search", "")
    page = action_data.get("page", 1)
    if action in ["clear_project_search"]:
        search_query = ""
        page = 1
    return [action, search_query, page]


def get_filtered_projects(projects: dict, search_query: str) -> list:
    """Get projects from action search with enhanced multi-field search."""
    if not search_query:
        return list(projects.items())

    all_projects = list(projects.items())
    search_query_lower = search_query.lower().strip()
    filtered_projects = []

    for project_id, project_data in all_projects:
        # Search across multiple fields
        searchable_fields = [
            project_data.get("name", ""),
            project_data.get("project_key", ""),
            project_data.get("project_id", ""),
        ]

        # Check if search query matches any field
        for field_value in searchable_fields:
            if field_value and search_query_lower in field_value.lower():
                filtered_projects.append((project_id, project_data))
                break  # Avoid duplicates if multiple fields match

    return filtered_projects


def _saving_project_field(projects: dict) -> list:
    """Get the necessary content of the project to save to the DB."""
    list_projects = []
    for idx, (pid, project) in enumerate(projects.items(), 1):
        list_projects.append(
            {
                "number": idx,
                "project_id": pid,
                "project_key": project.get("project_key") or "",
                "name": project.get("name") or "Unknown Project",
            },
        )
    return list_projects


def _saving_boards_field(boards: list) -> list:
    """Get the necessary content of the project to save to the DB."""
    list_boards = []
    for idx, board in enumerate(boards, 1):
        list_boards.append(
            {
                "number": idx,
                "board_id": board.get("id") or "",
                "board_name": board.get("name") or "",
            },
        )
    return list_boards
