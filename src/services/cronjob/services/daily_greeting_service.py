import psycopg
from botbuilder.schema import ConversationReference, ConversationAccount, ChannelAccount
from psycopg import errors

from src.config.settings import postgres_db_host, postgres_db_port, postgres_db_user, postgres_db_password


def dict_to_conversation_reference(data: dict) -> ConversationReference:
    return ConversationReference(
        channel_id=data["channelId"],
        service_url=data["serviceUrl"],
        conversation=ConversationAccount(id=data["conversation"]["id"]),
        bot=ChannelAccount(id=data["bot"]["id"]),
        user=ChannelAccount(id=data["user"]["id"], name=data["user"].get("name", ""))
    )
def parse_conversation_path(path: str):
    try:
        parts = path.split("/")
        if len(parts) != 4 or parts[2] != "conversations":
            return None
        return {
            "channel_id": parts[0],
            "bot_id": parts[1],
            "prefix": parts[2],
            "conversation_id": parts[3]
        }
    except Exception as e:
        print(f"Error parsing path: {e}")
        return None

def get_all_conversation_references() -> dict[str, ConversationReference]:
    connection = initialize_database_connection()
    references = {}

    select_query = "SELECT key, data FROM bot_state"

    try:
        with connection.cursor() as cursor:
            cursor.execute(select_query)
            results = cursor.fetchall()

            for key, data in results:
                try:
                    session_id = data.get("session_id",{})
                    data_info = data.get("conv_ref",{})
                    if not data_info:
                        continue
                    key_info = parse_conversation_path(key)
                    if key_info is None:
                        continue
                    ref = {
                        "bot": {"id": key_info["bot_id"]},
                        "user": {
                            "id": data_info["user_id"],
                            "name": data_info["user_name"]},
                        "conversation": {
                            "id": key_info["conversation_id"]
                        },
                        "channelId": key_info["channel_id"],
                        "serviceUrl": data_info["service_url"]
                    }
                    reference = dict_to_conversation_reference(ref)
                    references[session_id] = reference

                except Exception as parse_error:
                    print(f"[Warning] Failed to parse conversation reference for session_id {session_id}: {parse_error}")
    except Exception as e:
        raise RuntimeError(f"Failed to get all conversation references: {e}")
    finally:
        connection.close()

    return references

def load_config():
    return {
        "host": postgres_db_host,
        "port": postgres_db_port,
        "dbname": "rag_sync",
        "user": postgres_db_user,
        "password": postgres_db_password,
    }
def initialize_database_connection():
    try:
        return psycopg.connect(**load_config())
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}")