from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.bots.storage.postgres_storage import PostgresStorage
from src.config.fastapi_config import fastapi_settings

storage = PostgresStorage(connection_string=fastapi_settings.db.database_url)


def state_handler(bot_app):
    @bot_app.turn_state_factory
    async def turn_state_factory(context: TurnContext):
        return await AppTurnState.load(context, storage)
