from botbuilder.core import TurnContext

from src.adaptive_cards.card_utils import send_adaptive_card
from src.adaptive_cards.kb_cards import manage_jira_card
from src.bots.data_model.app_state import AppTurnState


async def handle_manage_jira(context: TurnContext, state: AppTurnState) -> str:
    """Handle the management of JIRA tickets."""
    _ = state
    await send_adaptive_card(context, manage_jira_card)
    return "Adaptive card sent to user successfully for managing JIRA"
