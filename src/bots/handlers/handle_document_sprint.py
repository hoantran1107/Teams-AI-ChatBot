import jsonpickle
from botbuilder.core import TurnContext
from teams.streaming import StreamingResponse

from src.adaptive_cards.card_utils import send_adaptive_card
from src.adaptive_cards.function_cards import create_input_document_sprint_card, create_input_list_sprints_card
from src.bots.data_model.app_state import AppTurnState
from src.services.cronjob.services.generate_sprint import generate_context, update_confluence
from src.services.jira_services.services.get_data import (
    get_all_board,
    get_all_field,
    get_all_sprint_in_board,
    get_issues_in_sprint_in_board_async,
)


async def handle_document_sprint(context: TurnContext, state: AppTurnState) -> None:
    """Handle Adaptive card action generate and upload document sprint to Confluence page."""
    _ = state
    # Get user input and fetch all projects
    activity_value = context.activity.value or {}
    action = activity_value.get("action")

    if action == "create_document_sprint" or action is None:
        # Display initial card with project selection
        projects = await get_all_board()
        input_card = create_input_document_sprint_card(projects=projects)
        await send_adaptive_card(context, input_card)

    elif action == "update_sprint_list":
        selected_board = activity_value.get("selected_board", "")
        board_data = jsonpickle.decode(selected_board) if selected_board else {}
        board_id = board_data.get("id", "")
        board_name = board_data.get("name", "")
        input_card = await create_input_list_sprints_card(board_id, board_name)
        await send_adaptive_card(context, input_card)

    elif action == "submit_sprint_data":
        board_name = activity_value.get("board_name", "")
        board_id = activity_value.get("board_id", "")
        confluence_page_id = activity_value.get("confluence_page_id", "")

        selected_sprint = activity_value.get("selected_sprint", "")
        sprint_data = jsonpickle.decode(selected_sprint) if selected_sprint else {}
        sprint_id = sprint_data.get("id", "")
        sprint_name = sprint_data.get("name", "")

        await process_sprint_submission(context, board_id, board_name, sprint_id, sprint_name, confluence_page_id)


async def process_sprint_submission(
    context: TurnContext,
    board_id: str,
    board_name: str,
    sprint_id: str,
    sprint_name: str,
    confluence_page_id: int,
) -> None:
    """Generate and Upload document sprint to Confluence page."""
    # Initialize streaming response for real-time feedback
    streamer = StreamingResponse(context)
    streamer.set_feedback_loop(True)
    streamer.set_generated_by_ai_label(True)

    # Fetch sprint details and find matching sprint
    streamer.queue_informative_update(f"🔍 Checking sprint {sprint_name}...\n\n")
    sprints = await get_all_sprint_in_board(int(board_id))
    sprint_info = sprints.get(sprint_id, {})
    if not sprint_info:
        streamer.queue_text_chunk(f"❌ Not found sprint **{sprint_name}** in {board_name}.")
        await streamer.wait_for_queue()
        await streamer.end_stream()
        return

    # Fetch tickets for the sprint
    streamer.queue_informative_update(f"🔍 Finding tickets for sprint {sprint_name}...\n\n")
    all_issue_fields = await get_all_field()
    tickets = await get_issues_in_sprint_in_board_async(int(board_id), int(sprint_id), all_issue_fields)
    if not tickets:
        streamer.queue_text_chunk(f"❌ No tickets found in sprint **{sprint_name}**.")
        await streamer.wait_for_queue()
        await streamer.end_stream()
        return

    # Generate sprint context and update Confluence
    streamer.queue_informative_update("📝 Generating Document Sprint...\n\n")
    response, tickets_id = await generate_context(sprint_info, tickets)
    sprint_context = response.content
    is_success, msg = await update_confluence(board_name, tickets_id, sprint_context, confluence_page_id)

    # Send success or error message
    if is_success:
        success_message = (
            f"✅ Successfully documented sprint '{sprint_name}' for project '{board_name}' with Confluence page: {msg}"
        )
        streamer.queue_text_chunk(success_message)
    else:
        error_message = f"❌ {msg}"
        streamer.queue_text_chunk(error_message)

    # Complete streaming response
    await streamer.wait_for_queue()
    await streamer.end_stream()
