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
from src.adaptive_cards.function_cards import create_ticket_items
from src.bots.data_model.app_state import AppTurnState
from src.config.settings import atlassian_jira_url
from src.constants.action_types import JiraActions
from src.constants.app_constants import AdaptiveCardConst, PagingConst
from src.services.jira_services.services.get_data import (
    get_all_field,
    get_issues_in_sprint_in_board_async,
)
from src.services.jira_services.services.jira_utils import extract_context_data


async def handle_list_tickets_action(context: TurnContext, state: AppTurnState) -> None:
    """Handle Adaptive card action List Jira Sprint."""
    board_id, board_name, project_key, sprint_id, sprint_name = extract_context_data(
        context,
        ["board_id", "board_name", "project_key", "sprint_id", "sprint_name"],
    )
    action_data = context.activity.value or {}
    action = action_data.get("action", "list_tickets")
    page = int(action_data.get("page", 1))

    all_issue_fields = await get_all_field()
    issues_dict = await get_issues_in_sprint_in_board_async(board_id, sprint_id, all_issue_fields)
    if not issues_dict:
        await context.send_activity(f"❌ No tickets found in sprint **{sprint_name}**.")
        return

    all_tickets = list(issues_dict.items())
    total_pages, page, start, end, page_tickets = get_pagination_details(
        all_tickets,
        PagingConst.PAGING_SIZE,
        page,
    )
    ticket_blocks = create_ticket_items(page_tickets, start)
    page_info, page_indicator = create_page_info(
        start,
        end,
        all_tickets,
        page,
        total_pages,
    )
    card_body = build_card_body(
        title=f"📋 Tickets in Sprint: **{sprint_name}**",
        page_info=page_info,
        page_indicator=page_indicator,
        items=ticket_blocks,
    )
    actions = build_paging_card(
        page,
        total_pages,
        JiraActions.LIST_TICKETS,
        {
            "board_id": board_id,
            "sprint_id": sprint_id,
            "project_key": project_key,
            "sprint_name": sprint_name,
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
    ticket_data = get_all_tickets_data(issues_dict)
    await handle_activity(
        context=context,
        state=state,
        action=action,
        target_action=JiraActions.LIST_TICKETS,
        activity=activity,
        state_key=JiraActions.STATE_TICKET,
        user_content=f"Ticket list of board: {board_name} and sprint: {sprint_name}",
        history_data=ticket_data,
    )


def get_all_tickets_data(tickets: dict) -> list:
    """Extract and format ticket data for display."""
    ticket_data = []
    for idx, (key, ticket) in enumerate(tickets.items(), 1):
        ticket_info = {
            "number": idx,
            "key": key,
            "status": ticket.get("Status", "Unknown"),
            "url": f"{atlassian_jira_url}/browse/{key}",
        }
        ticket_data.append(ticket_info)
    return ticket_data
