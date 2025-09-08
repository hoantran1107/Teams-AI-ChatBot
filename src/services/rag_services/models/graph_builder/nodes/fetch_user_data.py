from langchain_postgres import PostgresChatMessageHistory

from src.constants.db_constant import PG_CONN
from src.services.postgres.models.tables.rag_sync_db.chat_history_model import (
    ChatHistory,
)
from src.services.rag_services.models.graph_builder.nodes.save_instructions import (
    define_namespace_of_instructions,
    get_instruction_prompts,
)


async def fetch_conversation_data(conversation_id, k=20):
    """Fetches the last `k` chat messages and associated instruction prompts for a given conversation.

    Args:
        conversation_id (str): The unique identifier of the user.
        k (int, optional): The number of recent messages to fetch. Defaults to 20.

    Returns:
        tuple[list, list]: A tuple containing:
            - last_20_messages (list): A list of the last `k` chat messages for the user.
            - prompts (list): A list of instruction prompts associated with the user.

    """
    if not conversation_id:
        return [], []

    # Retrieve the chat message history for the user
    history = PostgresChatMessageHistory(
        ChatHistory.__tablename__,
        conversation_id,
        sync_connection=PG_CONN,
    )
    all_messages = history.messages
    last_20_messages = all_messages[-k:]
    del all_messages

    # Fetch the instruction prompts associated with the user
    namespace = define_namespace_of_instructions(conversation_id)
    prompts = get_instruction_prompts(namespace, format_as_bullet_points=True)

    return last_20_messages, prompts
