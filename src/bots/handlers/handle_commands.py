import re

from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.bots.handlers.commands import handle_command


def register_handle_commands(bot_app) -> None:
    """Register command handlers for the bot application."""

    @bot_app.message(re.compile(r"/(config|commands)", re.IGNORECASE))
    async def handle_commands(context: TurnContext, state: AppTurnState) -> None:
        await handle_command(context, state)
