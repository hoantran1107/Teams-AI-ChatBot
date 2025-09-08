import logging

from botbuilder.core import TurnContext

from src.adaptive_cards.card_utils import send_adaptive_card
from src.bots.data_model.app_state import AppTurnState
from src.bots.handlers.data_sources import handle_data_source_selection
from src.constants.app_constants import AdaptiveCardConst
from src.services.web_search_service.web_search_service import search_with_tavily

_logger = logging.getLogger(__name__)


def _is_web_search_enabled(state: AppTurnState) -> bool:
    user = getattr(state, "user", None)
    value = getattr(user, "web_search", None)
    if isinstance(value, str):
        return value.strip().lower() == "true"
    if isinstance(value, bool):
        return value
    return False


async def handle_web_search(context: TurnContext, state: AppTurnState) -> str:
    """Handle web search requests."""
    query = context.data.get("query", "")
    if not query:
        return "No search query provided"
    if not _is_web_search_enabled(state):
        return "Web search is currently disabled"
    try:
        # not  using ddg anymore: results = await WebSearchService().stream_search(query)
        response = await search_with_tavily(query)
        if not response:
            return "Web search completed but no relevant results found."
        return response
    except Exception as e:
        _logger.exception("Error in web search workflow")
        return f"Web search error: {e!s}"


async def handle_toggle_web_search(context: TurnContext, state: AppTurnState) -> str:
    """Toggle the web search feature on or off."""
    try:
        user = getattr(state, "user", None)
        if user is None:
            return "ERROR: No user state found."
        current = getattr(user, "web_search", "false")
        enabled = str(current).strip().lower() == "true"
        new_value = "false" if enabled else "true"
        user.web_search = new_value
        status = "Enabled" if new_value == "true" else "Disabled"
        emoji = "🌐" if new_value == "true" else "🚫"
        card_data = {
            "type": "AdaptiveCard",
            "version": AdaptiveCardConst.CARD_VERSION_1_4,
            "body": [
                {
                    "type": AdaptiveCardConst.TEXT_BLOCK,
                    "text": f"{emoji} Web Search {status}",
                    "weight": "Bolder",
                    "size": "Medium",
                },
                {
                    "type": AdaptiveCardConst.TEXT_BLOCK,
                    "text": f"Web search has been {status.lower()}.",
                    "wrap": True,
                },
            ],
        }
        await send_adaptive_card(context, card_data)
        await handle_data_source_selection(context, state)
        return f"SUCCESS: Web search has been {status.lower()}. The toggle operation completed successfully."
    except Exception as e:
        _logger.exception("Error in toggle web search workflow")
        return f"ERROR: Failed to toggle web search. Error: {e!s}"
