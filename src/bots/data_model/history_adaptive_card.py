from typing import Any

import jsonpickle
from teams.ai.prompts.message import Message

from src.bots.data_model.app_state import AppTurnState

jsonpickle.set_preferred_backend("json")
jsonpickle.set_encoder_options("json", ensure_ascii=False, indent=2)


def save_history(state: AppTurnState, user_content: str, response: Any) -> None:
    """Save response of adaptive card to DB."""
    if "chat_history" not in state.conversation:
        state.conversation.chat_history = []

    state.conversation.chat_history.append(Message(role="user", content=jsonpickle.encode(user_content)))
    state.conversation.chat_history.append(Message(role="assistant", content=jsonpickle.encode(response)))
