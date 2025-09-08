from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ActivityTypes, Attachment

from src.adaptive_cards.card_utils import (
    build_card_body,
    build_paging_card,
    create_basic_card,
    create_page_info,
    get_pagination_details,
    handle_activity,
)
from src.adaptive_cards.function_cards import create_sprint_items
from src.bots.data_model.app_state import AppTurnState
from src.config.settings import atlassian_jira_url
from src.constants.action_types import JiraActions
from src.constants.app_constants import AdaptiveCardConst
from src.services.jira_services.services.get_data import get_all_sprint_in_board
from src.services.jira_services.services.jira_utils import extract_context_data

SPRINTS_PER_PAGE = 10


async def handle_list_sprints_action(context: TurnContext, state: AppTurnState) -> None:
    """Handle Adaptive card action List Jira Sprint."""
    board_id, board_name, project_id, project_key = extract_context_data(
        context,
        ["board_id", "board_name", "project_id", "project_key"],
    )
    action_data = context.activity.value or {}
    action = action_data.get("action", "list_sprints")
    page = int(action_data.get("page", 1))

    sprints = await get_all_sprint_in_board(board_id)
    if not sprints:
        await context.send_activity(f"❌ No sprints found in board {board_name}.")
        return

    all_sprints = list(sprints.items())
    all_sprints.reverse()
    total_pages, page, start, end, page_sprints = get_pagination_details(all_sprints, SPRINTS_PER_PAGE, page)
    sprint_items = create_sprint_items(page_sprints, start, board_id, board_name, project_key)
    page_info, page_indicator = create_page_info(start, end, all_sprints, page, total_pages)
    card_body = build_card_body(
        title=f"**List Sprint for Board: {board_name}**",
        page_info=page_info,
        page_indicator=page_indicator,
        items=sprint_items,
    )
    actions = build_paging_card(
        page,
        total_pages,
        JiraActions.LIST_SPRINTS,
        {
            "board_id": board_id,
            "board_name": board_name,
            "project_id": project_id,
            "project_key": project_key,
        },
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

    sprint_data = get_all_sprint_data(all_sprints, board_name, board_id, project_key)
    await handle_activity(
        context=context,
        state=state,
        action=action,
        target_action=JiraActions.LIST_SPRINTS,
        activity=activity,
        state_key=JiraActions.STATE_SPRINT,
        user_content=f"List of sprint in board: {board_name}",
        history_data=sprint_data,
    )


def get_all_sprint_data(
    sprints: list,
    board_name: str,
    board_id: int,
    project_key: str,
) -> list:
    """Get the necessary content of the Sprints to save to the DB."""
    sprint = []
    for idx, (sprint_id, sprint_data) in enumerate(sprints, 1):
        sprint_name = sprint_data.get("name") or ""
        sprint_state = sprint_data.get("state") or ""
        if sprint_state == "closed":
            url = f"{atlassian_jira_url}/jira/software/c/projects/{project_key}/boards/{board_id}/reports/sprint-retrospective?sprint={sprint_id}"
        else:
            url = f"{atlassian_jira_url}/jira/software/c/projects/{project_key}/boards/{board_id}/backlog"
        sprint.append(
            {
                "number": idx,
                "sprint_id": sprint_id,
                "name": sprint_name,
                "state": sprint_state,
                "board_id": board_id,
                "board_name": board_name,
                "url": url,
            },
        )

    return sprint
