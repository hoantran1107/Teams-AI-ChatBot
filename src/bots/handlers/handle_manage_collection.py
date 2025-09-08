from botbuilder.core import MessageFactory, TurnContext
from botbuilder.schema import Attachment

from src.adaptive_cards.kb_cards import manage_collections_card
from src.bots.data_model.app_state import AppTurnState
from src.constants.app_constants import AdaptiveCardConst


async def handle_manage_collections(context: TurnContext, state: AppTurnState) -> str:
    """Handle the management of knowledge collections."""
    _ = state
    await context.send_activity(MessageFactory.attachment(Attachment(
        content_type=AdaptiveCardConst.CONTENT_TYPE,
        content=manage_collections_card,
    )))
    return "Adaptive card sent to user successfully for managing Knowledge Collections"
