import json
from collections.abc import Awaitable, Callable
from typing import Any

from botbuilder.core import BotFrameworkAdapterSettings
from botbuilder.core.turn_context import TurnContext
from botbuilder.schema import Activity, ResourceResponse
from teams import TeamsAdapter


class ConsoleAdapter(TeamsAdapter):
    """A console adapter for testing that captures bot responses."""

    def __init__(self) -> None:
        """Initialize the ConsoleAdapter."""
        super().__init__(BotFrameworkAdapterSettings("", ""))
        self.responses: list[dict[str, Any]] = []

    async def send_activities(self, context: TurnContext, activities: list[Activity]) -> list[ResourceResponse]:
        """Capture outgoing activities instead of sending them."""
        for activity in activities:
            if activity.type == "message":
                self.responses.append(activity.as_dict())
        return [ResourceResponse(id=activity.id) for activity in activities]

    async def run_bot(
        self, activity: Activity, bot_callback: Callable[[TurnContext], Awaitable]
    ) -> dict[str, Any] | None:
        """Process an incoming activity and return the bot's response."""
        self.responses = []  # Clear previous responses
        context = TurnContext(self, activity)
        await bot_callback(context)

        if self.responses:
            # Return the first response content
            response_activity = self.responses[0]
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": response_activity.get("text", ""),
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
        return None
