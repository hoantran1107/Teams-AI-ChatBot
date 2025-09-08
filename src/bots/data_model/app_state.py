from typing import Optional, List, Dict
from datetime import datetime

from botbuilder.core import Storage, TurnContext
from teams.state import ConversationState, TempState, TurnState, UserState
from src.bots.data_model.user_state import EnhancedUserState


class AppTurnState(TurnState[ConversationState, EnhancedUserState, TempState]):
    @classmethod
    async def load(
        cls, context: TurnContext, storage: Optional[Storage] = None
    ) -> "AppTurnState":
        return cls(
            conversation=await ConversationState.load(context, storage),
            user=await UserState.load(context, storage),
            temp=await TempState.load(context, storage),
        )
    def ensure_data_sources_exists(self) -> None:
        if "data_sources" not in self.user.data_sources:
            self.user.data_sources = []
    def get_user_name(self) -> None:
        if "user_name" not in self.user:
            self.user.user_name = None