import json
import logging
import traceback
from datetime import datetime

from botbuilder.core import TurnContext
from botbuilder.core.turn_context import timezone
from teams.app_error import ApplicationError

from src.adaptive_cards.card_utils import create_error_card, send_adaptive_card
from src.constants.app_constants import AdaptiveCardConst

_logger = logging.getLogger(__name__)


def register_error_handler(bot_app) -> None:
    """Register error handler for the bot application."""

    @bot_app.error
    async def on_error(context: TurnContext, error: Exception):
        """Handle an error."""
        error_id = f"ERR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        # Extract the actual error message from nested structure
        error_message = str(error)
        if (
            isinstance(error, ApplicationError)
            and str(error) == "(ContentStreamNotAllowed) Content stream was cancelled by user."
        ):
            return
        # Log structured error information
        error_details = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat(),
            "user_message": context.activity.text if hasattr(context.activity, "text") else "No message",
        }
        _logger.error(f"\n[ERROR] {json.dumps(error_details)}")
        _logger.error(traceback.format_exc())

        card = create_error_card(
            title="⚠️ Something went wrong",
            message=f"I encountered an error (ID: {error_id}). Please try again or contact support if the issue persists.\n{error_message}",
        )
        action: dict = {
            "actions": [
                {
                    "type": AdaptiveCardConst.ACTION_SUBMIT,
                    "title": "New Chat",
                    "data": {"action": "new_chat"},
                },
            ],
        }
        card.update(action)
        await send_adaptive_card(context, card)
