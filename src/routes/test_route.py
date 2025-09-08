import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from botbuilder.schema import Activity, ChannelAccount
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response

from src.bots.ai_bot import bot_app
from src.bots.console_adapter import ConsoleAdapter

logger = logging.getLogger(__name__)

# Create a dedicated logger for red teaming interactions
red_team_logger = logging.getLogger("red_teaming_interactions")
red_team_logger.setLevel(logging.INFO)

# Create log directory if it doesn't exist
log_dir = Path("red_team_logs")
log_dir.mkdir(exist_ok=True)

# Create file handler with timestamp
log_filename = log_dir / f"red_team_interactions_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"
file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# Create detailed formatter for red team logs
red_team_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(red_team_formatter)
red_team_logger.addHandler(file_handler)

# Prevent propagation to avoid duplicate logs
red_team_logger.propagate = False


def add_test_route_fastapi(app: FastAPI) -> FastAPI:
    """Add a test endpoint that bypasses authentication for testing with tools like NVIDIA garak."""
    router = APIRouter()

    # Create a console adapter for testing
    console_adapter = ConsoleAdapter()

    @router.post("/chat/completions", tags=["Testing"])
    async def test_messages(request: Request, deployment_name: str | None = None) -> Response:
        """Test endpoint that allows sending messages to the bot without authentication.

        Supports both direct test messages and Azure OpenAI style endpoints.
        This is for testing purposes only and should not be exposed in production.
        """
        del deployment_name  # Unused
        try:
            body = await request.json()

            # Handle both OpenAI chat format and Bot Framework Activity format
            if isinstance(body, dict) and "messages" in body:
                # OpenAI chat format
                last_message = body["messages"][-1]["content"] if body["messages"] else ""
                # Create an Activity with the text as content
                activity = Activity(
                    type="message",
                    text=last_message,
                    service_url="http://localhost:5000",  # Dummy service URL for local testing
                    channel_id="test",
                    conversation=ChannelAccount(id="test-conversation"),
                    recipient=ChannelAccount(id="bot", name="Bot"),
                    from_property=ChannelAccount(id="user", name="User"),
                )
            else:
                # Bot Framework Activity format
                try:
                    activity = Activity().deserialize(body)
                    last_message = activity.text or ""
                except (ValueError, TypeError, KeyError) as e:
                    logger.error(f"Invalid request body format: {e}")
                    raise HTTPException(status_code=400, detail="Invalid request body format") from e

            # Log the incoming request
            red_team_logger.info("=" * 80)
            red_team_logger.info("RED TEAM INTERACTION")
            red_team_logger.info(f"INPUT: {last_message}")

            # Process the activity with our console adapter
            response_data = await console_adapter.run_bot(activity, bot_app.on_turn)

            if response_data:
                # Extract the bot's response for logging
                bot_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "No response")

                # Log the bot's response
                red_team_logger.info(f"OUTPUT: {bot_response}")
                red_team_logger.info("=" * 80)

                return Response(
                    content=json.dumps(response_data),
                    media_type="application/json",
                )
            # Log when no response is generated
            red_team_logger.info("OUTPUT: No response generated")
            red_team_logger.info("RESPONSE_DATA: null")
            red_team_logger.info("=" * 80)

            return Response(status_code=202)
        except Exception as e:
            logger.exception("Error during test processing")
            return Response(content=f"Test Error: {e!s}", status_code=500)

    app.include_router(router)
    return app
