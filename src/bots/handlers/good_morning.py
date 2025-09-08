from botbuilder.core import TurnContext
from teams import TeamsAdapter

from src.bots.ai_bot import bot_app
from src.bots.data_model.app_state import AppTurnState


async def send_proactive_hello(adapter: TeamsAdapter, conversation_reference):
    async def continue_callback(context: TurnContext):
        state = AppTurnState()
        await context.send_activity("☀️ Good morning! Wishing you a great start to your day.")
        # To Do: Send proactive message to user
        

    await adapter.continue_conversation(
        conversation_reference,
        continue_callback,
        bot_app.options.bot_app_id
    )




