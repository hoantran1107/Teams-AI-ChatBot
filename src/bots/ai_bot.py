import logging
import os
import shutil
import uuid

from botbuilder.core import TurnContext
from botbuilder.core.memory_storage import MemoryStorage
from botbuilder.schema import ActivityTypes

# Teams imports
from teams import Application, ApplicationOptions, TeamsAdapter
from teams.adaptive_cards.adaptive_cards_options import AdaptiveCardsOptions
from teams.ai import AIOptions
from teams.ai.models import AzureOpenAIModelOptions, OpenAIModel
from teams.ai.planners import ActionPlanner, ActionPlannerOptions
from teams.ai.prompts import PromptManager, PromptManagerOptions

from src.adaptive_cards.function_cards import check_and_send_unsupported_card
from src.bots.data_model.app_state import AppTurnState
from src.bots.handlers.attachment import (
    TEMP_FILE_DIRECTORY,
    ask_for_choosing_collection,
)

# Bot framework imports
from src.bots.handlers.commands import handle_command
from src.bots.handlers.data_sources import handle_data_source_selection
from src.bots.handlers.dispatcher import dispatch_submit_action
from src.bots.handlers.error import register_error_handler
from src.bots.handlers.feedback import register_feedback_handler
from src.bots.handlers.greeting import handle_clear_chat_history
from src.bots.handlers.handler_n8n_mcp import handle_n8n_mcp_request
from src.bots.handlers.manage_collection import handle_create_collection_request

# Local imports
from src.bots.handlers.modify_collection_pages import (
    handle_add_page_request,
    handle_remove_page_request,
    handle_show_page_request,
)
from src.bots.handlers.rag_process import handle_rag_query
from src.bots.handlers.reaction import register_reaction_handlers
from src.bots.handlers.submit_action import register_handle_submit_actions
from src.bots.handlers.web_search_handler import (
    handle_toggle_web_search,
    handle_web_search,
)
from src.bots.storage.postgres_storage import PostgresStorage
from src.config.ai_config import ai_config
from src.config.bot_config import BotConfig
from src.constants.docling_constant import DoclingConstant

logger = logging.getLogger()
# Delete the temp folder directory if it exists
if os.path.exists(TEMP_FILE_DIRECTORY):
    try:
        # Remove all files or folder in the directory regardless of the type
        shutil.rmtree(TEMP_FILE_DIRECTORY)
    except OSError as e:
        logger.error(f"Error deleting temp directory: {e}")

model = OpenAIModel(
    AzureOpenAIModelOptions(
        api_key=ai_config.azure.api_key,
        default_model=ai_config.azure.azure_openai_model_deployment_name,
        endpoint=ai_config.azure.azure_openai_endpoint,
        stream=True,
        logger=logger,
    ),
)

prompts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts"))
prompts = PromptManager(
    PromptManagerOptions(prompts_folder=prompts_path, max_history_messages=BotConfig.MAX_HISTORY_MESSAGES),
)

planner = ActionPlanner(
    ActionPlannerOptions(
        model=model,
        prompts=prompts,
        default_prompt="chat",
        enable_feedback_loop=True,
        logger=logger,
    ),
)
memory = MemoryStorage()
storage = PostgresStorage(connection_string=BotConfig.POSTGRES_CONNECTION_STRING)
# Create singleton instance of the bot adapter
bot_app = Application[AppTurnState](
    ApplicationOptions(
        bot_app_id=BotConfig.APP_ID,
        # Register the storage and adapter
        storage=storage,
        adapter=TeamsAdapter(BotConfig),
        adaptive_cards=AdaptiveCardsOptions(action_submit_filer="action"),
        ai=AIOptions(planner=planner, allow_looping=True, enable_feedback_loop=True),
    ),
)


@bot_app.activity(ActivityTypes.message)
async def handle_all_messages(context: TurnContext, state: AppTurnState):
    """Main entry point for handling all incoming messages from users."""
    # Save user info to db
    reference = TurnContext.get_conversation_reference(context.activity)
    session_id = state.conversation.get("session_id")
    user_name = reference.user.name if reference.user else None

    if not session_id:
        session_id = str(uuid.uuid4())
        state.conversation.session_id = session_id

    if "user_name" not in state.user:
        state.user.user_name = user_name
    if "conv_ref" not in state.conversation:
        state.conversation.conv_ref = {
            "bot_name": reference.bot.name if reference.bot else None,
            "user_id": reference.user.id if reference.user else None,
            "user_name": user_name,
            "service_url": reference.service_url,
        }
    try:
        # 1. Handle Adaptive Card submissions first
        if context.activity.value and isinstance(context.activity.value, dict):
            action = context.activity.value.get("action")
            if action:
                await dispatch_submit_action(action, context, state)
                return

        # 2. Extract uploaded files with supported Teams file content type
        uploaded_files = [
            item
            for item in (context.activity.attachments or [])
            if item.content_type == "application/vnd.microsoft.teams.file.download.info"
        ]

        if uploaded_files:
            if await check_and_send_unsupported_card(context, uploaded_files):
                await ask_for_choosing_collection(context, uploaded_files)
            return

        # 3. Handle text messages
        if context.activity.text:
            if context.activity.text.startswith(("/commands", "/config")):
                await bot_app.ai.do_action(context, state, action="get_supported_commands")
                return

            # Default: pass to AI planner
            await bot_app.ai.run(context, state)
            return

        # 4. Handle case of sending only file but not found in attachment or sending only icon
        allowed_file_type_string = ", ".join(map(lambda x: x.removeprefix("."), DoclingConstant.SUPPORTED_FILES))
        if context.activity.attachments and len(context.activity.attachments) == 1:
            _ = await context.send_activity(
                f"❌ Sorry, I can't read this file. Please send a file in {allowed_file_type_string} format.\n\n"
                "📋 **Note:** Teams bots don't support files linked from other SharePoint sites.\n\n"
                "💡 **Tip:** Upload the file directly to this Teams chat instead.",
            )
        else:
            _ = await context.send_activity(
                "🤖 I can only process text messages or supported files. Please send valid content. "
                "📄 **Supported files:** " + allowed_file_type_string,
            )

    except Exception as e:
        logger.error("Error in handle_all_messages: %s", e, exc_info=True)
        raise


# Register the AI actions with the bot application
bot_app.ai.action("n8n_mcp")(handle_n8n_mcp_request)
bot_app.ai.action("show_document")(handle_show_page_request)
bot_app.ai.action("remove_document")(handle_remove_page_request)
bot_app.ai.action("add_document")(handle_add_page_request)
bot_app.ai.action("data_sources")(handle_data_source_selection)
bot_app.ai.action("rag_query")(handle_rag_query)
bot_app.ai.action("web_search")(handle_web_search)
bot_app.ai.action("toggle_web_search")(handle_toggle_web_search)
bot_app.ai.action("create_collection_request")(handle_create_collection_request)
bot_app.ai.action("clear_history")(handle_clear_chat_history)
bot_app.ai.action("get_supported_commands")(handle_command)
# Register all handlers
register_feedback_handler(bot_app)
register_error_handler(bot_app)
register_reaction_handlers(bot_app)
register_handle_submit_actions(bot_app)
