from botbuilder.core import TurnContext

from src.adaptive_cards.card_utils import send_adaptive_card
from src.adaptive_cards.kb_cards import commands_card, supported_commands
from src.bots.data_model.app_state import AppTurnState


async def handle_command(context: TurnContext, state: AppTurnState) -> str:
    """Handle user command and show supported commands."""
    _ = state
    await send_adaptive_card(context, commands_card)
    return (
        f"Adaptive card sent to user successfully with list of supported commands: {supported_commands}"
        "No return list of supported commands, just show adaptive card to user"
    )
