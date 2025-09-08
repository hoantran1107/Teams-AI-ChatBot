from botbuilder.core import TurnContext

from src.adaptive_cards.card_utils import create_error_card, create_success_card, send_adaptive_card
from src.adaptive_cards.kb_cards import create_collection_card
from src.bots.data_model.app_state import AppTurnState
from src.bots.storage.postgres_storage import PostgresStorage
from src.config.fastapi_config import fastapi_settings
from src.constants.app_constants import AdaptiveCardConst
from src.services.manage_rag_sources.services.manage_source import ManageSource

# Use the new configuration system to get the database URL
storage = PostgresStorage(connection_string=fastapi_settings.db.database_url)


async def handle_create_collection_request(context: TurnContext, state: AppTurnState) -> str :
    """Handles requests to create a new collection."""
    # Start a multi-turn conversation to collect the information
    if "create_collection_flow" not in state.user:
        state.user.create_collection_flow = {
            "active": True,
            "step": "start",
        }

    # Create and send the collection creation card
    await send_adaptive_card(context, create_collection_card)

    return ""


async def handle_collection_actions(context: TurnContext, state: AppTurnState) -> None:
    """Handle actions from collection creation adaptive card."""
    action = context.activity.value.get("action", "")
    user_state = state.user

    if action == "create_collection_submit":
        return await process_collection_creation(context, user_state)
    return None


async def process_collection_creation(context: TurnContext, user_state) -> None:
    """Process the submitted collection creation form."""
    # Get values from the form
    value = context.activity.value or {}
    source_name = value.get("collectionName", "")
    note = value.get("note", "")

    # Get user ID from context
    user_id = context.activity.from_property.id

    await context.send_activity("Creating collection, please wait...")

    try:
        # Direct method call instead of API call
        new_collection_info: dict = ManageSource.add_source(
            source_name=source_name,
            note=note,
            user_id=user_id,
        )

        if new_collection_info:
            # Add note/description if it was provided
            if note:
                success_card_body = create_success_card(
                    title="✅ Collection Created Successfully",
                    message=f"Collection **{source_name}** has been created successfully.",
                    additional_items=[
                        {
                            "type": AdaptiveCardConst.TEXT_BLOCK,
                            "text": "Description:",
                            "wrap": True,
                            "spacing": "Medium",
                            "weight": "Bolder",
                        },
                        {"type": AdaptiveCardConst.TEXT_BLOCK, "text": note, "wrap": True, "isSubtle": True},
                    ],
                )
            else:
                success_card_body = create_success_card(
                    title="✅ Collection Created Successfully",
                    message=f"Collection **{source_name}** has been created successfully.",
                )

            await send_adaptive_card(context, success_card_body)
        else:
            card = create_error_card("Collection Creation Failed", "Could not create the collection. Please try again.")
            await send_adaptive_card(context, card)

    except Exception as e:
        card = create_error_card("Collection Creation Failed", f"An error occurred: {e!s}")
        await send_adaptive_card(context, card)

    # Reset the flow
    if "create_collection_flow" in user_state:
        del user_state["create_collection_flow"]
