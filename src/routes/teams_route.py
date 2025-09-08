import json
import logging
from typing import Annotated, Any

from botbuilder.schema import Activity
from fastapi import APIRouter, FastAPI, Header, HTTPException, Request, Response
from pydantic import RootModel

from src.bots.ai_bot import bot_app
from src.constants.app_constants import MIME_TYPE

logger = logging.getLogger(__name__)


class ActivityModel(RootModel):
    """Pydantic model for Teams activity payload."""

    model_config = {"arbitrary_types_allowed": True}
    root: dict[str, Any]


def add_teams_route_fastapi(app: FastAPI) -> FastAPI:
    """Add Teams messaging route to the FastAPI application."""
    # This function is called in the main.py file to add the Teams route to the FastAPI app

    router = APIRouter()

    @router.post("/api/messages")
    async def messages(request: Request, authorization: Annotated[str | None, Header()] = None) -> Response:
        """FastAPI route to handle incoming messaging endpoint requests from the Bot Framework Service."""
        content_type = request.headers.get("Content-Type", "")
        if MIME_TYPE not in content_type:
            logger.error(f"Unsupported Content-Type: {content_type}")
            raise HTTPException(status_code=415, detail="Unsupported Media Type")

        body = await request.json()
        activity = Activity().deserialize(body)
        auth_header = authorization or ""

        try:
            # Process the activity with the bot adapter
            response = await bot_app.adapter.process_activity(
                auth_header,
                activity,
                bot_app.on_turn,
            )
            if response:
                content = response.body
                # Check the data type of response.body
                if not isinstance(content, (str, bytes)):
                    content = json.dumps(content)

                return Response(
                    content=content,
                    status_code=response.status,
                    media_type=MIME_TYPE,
                )
            # If adapter didn't send a response, return Accepted (202)
            return Response(status_code=202)
        except Exception:
            logger.exception("Error during adapter processing.")
            return Response(content="Internal Server Error", status_code=500)

    # Add the router to the FastAPI app
    app.include_router(router)
    return app
