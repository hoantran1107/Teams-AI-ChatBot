from botbuilder.core import TurnContext

from src.adaptive_cards.card_utils import send_adaptive_card
from src.adaptive_cards.data_source_setting import get_data_source_settings
from src.bots.data_model.app_state import AppTurnState
from src.bots.data_model.history_adaptive_card import save_history
from src.services.manage_rag_sources.services.manage_source import ManageSource


async def handle_data_source_selection(context: TurnContext, state: AppTurnState) -> str:
    """Handle data source selection and display the adaptive card."""
    # Get previously selected data sources
    empty_selected_options = {"common": [], "user": []}
    if "data_sources" in state.user:
        selected_options = state.user.data_sources
        if not isinstance(selected_options, dict):
            selected_options = empty_selected_options
    else:
        selected_options = empty_selected_options

    # Get user-specific sources
    user_id = context.activity.from_property.id
    user_sources = ManageSource.get_source_name_by_user_id(user_id)

    # Get common sources - make sure to get the actual Collection objects, not just names
    common_sources = ManageSource.get_common_source_names()
    common_source_names = [source.name for source in common_sources]

    # Add all available sources to selected options if none are selected yet
    if not selected_options:
        selected_options = {"common": common_source_names, "user": []}
        if user_sources:
            user_source_names = [source.name for source in user_sources]
            selected_options["user"] = user_source_names

    # Get user preferences
    analysis_mode = state.user.analysis_mode if "analysis_mode" in state.user else False
    web_search = state.user.web_search if "web_search" in state.user else False

    # Prepare common collections choices
    common_choices = [
        {"title": source.name, "value": {"source_name": source.name, "user_id": None}} for source in common_sources
    ]

    # Prepare user-specific collections choices
    user_choices = [
        {
            "title": source.name,
            "value": {"source_name": source.name, "user_id": user_id},
        }
        for source in user_sources
    ]

    await send_adaptive_card(
        context=context,
        card=get_data_source_settings(common_choices + user_choices, selected_options, analysis_mode, web_search),
    )

    return "Action completed it just show adaptive card"


async def update_data_sources(context: TurnContext, state: AppTurnState) -> None:
    """Update Adaptive card data sources based on user selection."""
    if context.activity.value and isinstance(context.activity.value, dict):
        # Get common collections
        common_options = context.activity.value.get("commonOptions", "")
        # Get user collections
        user_options = context.activity.value.get("userOptions", "")

        # Process common collections
        common_selected = common_options.split(",") if common_options else []
        # Process user collections
        user_selected = user_options.split(",") if user_options else []  # Update user state
        if common_selected or user_selected:
            state.user.data_sources = {"common": common_selected, "user": user_selected}

            # Create an engaging message with emojis and formatting
            message_parts = ["🎯 **Data Sources Updated Successfully!**\n"]

            if common_selected:
                message_parts.append(f"📊 **Common Sources:** {', '.join(common_selected)}")
            if user_selected:
                message_parts.append(f"👤 **Your Sources:** {', '.join(user_selected)}")
        else:
            state.user.data_sources = []
            message_parts = ["⚠️ **No data sources selected** - Please select at least one source for better results!"]

        # Update preferences
        state.user.analysis_mode = context.activity.value.get("analysisMode", False)
        state.user.web_search = context.activity.value.get("webSearch", False)

        # Add settings info with emojis
        message_parts.append("\n⚙️ **Settings:**")
        message_parts.append(
            f"   🔍 Analysis Mode: {'✅ Enabled' if state.user.analysis_mode == 'true' else '❌ Disabled'}",
        )
        message_parts.append(f"   🌐 Web Search: {'✅ Enabled' if state.user.web_search == 'true' else '❌ Disabled'}")

        final_message = "\n".join(message_parts)

        await context.send_activity(final_message)
        save_history(
            state,
            "User have selected data sources/infomation collections for knownledge base rag query",
            final_message,
        )
    else:
        await context.send_activity("Invalid selection. Please try again.")
