from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState


def register_reaction_handlers(bot_app):
    @bot_app.message_reaction("reactionsAdded")
    async def handle_reaction(context: TurnContext, state: AppTurnState):
        print("reaction added")
        await context.send_activity("Reaction received")
