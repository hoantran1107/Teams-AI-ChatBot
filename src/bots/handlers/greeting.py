import logging

from botbuilder.core import TurnContext

from src.adaptive_cards.card_utils import send_adaptive_card
from src.adaptive_cards.kb_cards import clear_chat_history_card, clear_history_error_card, kb_guide
from src.bots.data_model.app_state import AppTurnState
from src.services.rag_services.services import RAGService  # Add this import

_logger = logging.getLogger(__name__)


async def handle_clear_chat_history(context: TurnContext, state: AppTurnState) -> str:
    """Clear chat history and start fresh with new session."""
    try:
        if "chat_history" not in state.conversation:
            state.conversation.chat_history = []

        if context.activity.value:
            state.conversation.chat_history.clear()
            # Send a card instead of text to prevent AI Planner from generating text response
            await send_adaptive_card(context, clear_chat_history_card)
            return ""

        history_action = state.conversation.chat_history[-2:]
        state.conversation.chat_history.clear()
        # Save user content in db
        state.conversation.chat_history.extend(history_action)
        return "History cleared successfully. Return chat history cleared successfully and next your action"

    except Exception as e:
        _logger.error("Error clearing chat history: %s", e)
        # Send a card instead of text
        await send_adaptive_card(context, clear_history_error_card)
        return "Error clearing history, but you can continue chatting."


async def handle_new_chat(context: TurnContext, state: AppTurnState) -> None:
    """Reset the conversation and start a new chat."""
    # Check if this is a button click with action data
    if hasattr(context.activity, "value") and isinstance(context.activity.value, dict):
        if context.activity.value.get("action") == "new_chat":
            if hasattr(state, "conversation"):
                del state.conversation
            await context.send_activity("Starting a new conversation!")
            await handle_new_member(context, state)

    # Handle plain text "New chat" message
    if hasattr(state, "conversation"):
        del state.conversation
    await context.send_activity("Starting a new conversation!")
    await handle_new_member(context, state)


async def handle_reset(context: TurnContext, state: AppTurnState) -> None:
    """Complete reset to new user state."""
    # Clear chat history in database
    session_id = state.conversation.get("session_id") if state.conversation else None
    if session_id and session_id.strip():
        RAGService.clear_history(session_id)

    # Reset conversation state completely
    if hasattr(state, "conversation"):
        del state.conversation

    # Reset user state completely (preferences, history, etc.)
    if hasattr(state, "user") and state.user:
        # Clear user preferences
        state.user.data_sources = None
        state.user.analysis_mode = False
        state.user.web_search = False
        state.user.question_history = []

        # Clear activity IDs
        activity_attrs = ["list_projects_activity_id"]  # Add other activity IDs
        for attr in activity_attrs:
            if hasattr(state.user, attr):
                delattr(state.user, attr)

    await context.send_activity("🔄 Complete reset done! Starting fresh as a new user.")

    # Initialize as completely new user
    await handle_new_member(context, state)


# Common intents
# Greetings
# Help
async def handle_new_member(context: TurnContext, state: AppTurnState) -> None:
    """Handle new member joining the conversation."""
    _ = state
    # Send welcome card
    await send_adaptive_card(context, kb_guide)
