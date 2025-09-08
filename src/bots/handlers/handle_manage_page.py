from botbuilder.core import TurnContext

from src.adaptive_cards.card_utils import send_adaptive_card
from src.adaptive_cards.kb_cards import manage_pages_card
from src.bots.data_model.app_state import AppTurnState


async def handle_manage_pages(context: TurnContext, state: AppTurnState) -> str:
    """Handle the management of Confluence pages."""
    _ = state
    await send_adaptive_card(context, manage_pages_card)
    return "Adaptive card sent to user successfully for managing Confluence pages"
