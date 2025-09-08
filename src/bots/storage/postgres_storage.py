from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Dict, List, Optional, Any
import json
import asyncpg
import os
import logging
from dataclasses import dataclass
from botbuilder.core.storage import Storage, StoreItem
from teams.ai.prompts.message import Message
import jsonpickle

logger = logging.getLogger(__name__)

jsonpickle.set_preferred_backend("json")
jsonpickle.set_encoder_options("json", ensure_ascii=False, indent=2)


@dataclass
class StorageConfig:
    """Configuration for storage"""

    connection_string: Optional[str]
    table_name: str = "bot_state"
    max_connections: int = 10
    min_connections: int = 2
    max_inactive_connection_lifetime: float = 300.0


class StorageSerializer(ABC):
    """Abstract base class for storage serialization"""

    @abstractmethod
    def serialize(self, value: Any) -> str:
        pass

    @abstractmethod
    def deserialize(self, data: str) -> Any:
        pass


class JsonStorageSerializer(StorageSerializer):
    """JSON-based storage serializer"""

    def serialize(self, value: Any) -> str:
        return json.dumps(value)

    def deserialize(self, data: str) -> Any:
        return json.loads(data)


class ConnectionManager:
    """Manages database connection pool"""

    def __init__(self, config: StorageConfig):
        self.config = config
        self._pool = None

    async def ensure_connection(self):
        """Ensures the database connection pool is created"""
        if self._pool is None:
            try:
                logger.info("Creating connection pool to PostgreSQL")
                # Create a connection pool with the provided configuration
                self._pool = await asyncpg.create_pool(
                    self.config.connection_string,
                    min_size=self.config.min_connections,
                    max_size=self.config.max_connections,
                    max_inactive_connection_lifetime=self.config.max_inactive_connection_lifetime,
                    command_timeout=60.0,
                    server_settings={"search_path": "ifd_rag_data, public"},
                )

            except Exception as e:
                logger.error(f"Error creating connection pool: {str(e)}")
                raise

    async def close(self):
        """Close the connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self):
        return self._pool


class MessageConverter:
    """Handles conversion between Message objects and dictionaries"""

    @staticmethod
    def to_dict(message: Message) -> Dict:
        return {
            "role": message.role,
            "content": message.content,
            "context": message.context,
            "function_call": message.function_call,
            "name": message.name,
            "action_calls": (
                message.action_calls if hasattr(message, "action_calls") else []
            ),
            "action_call_id": message.action_call_id,
        }

    @staticmethod
    def from_dict(data: Dict) -> Message:
        return Message(
            role=data.get("role") or "user",
            content=data.get("content"),
            context=data.get("context"),
            function_call=data.get("function_call"),
            name=data.get("name"),
            action_calls=data.get("action_calls", []),
            action_call_id=data.get("action_call_id"),
        )


class PostgresStorage(Storage):
    """PostgreSQL Storage implementation for Bot State"""

    def __init__(self, connection_string: Optional[str] = None):
        config = StorageConfig(
            connection_string=connection_string,
            table_name=os.environ.get("POSTGRES_TABLE_NAME", "bot_state"),
            max_connections=int(os.environ.get("POSTGRES_MAX_CONNECTIONS", "10")),
            min_connections=int(os.environ.get("POSTGRES_MIN_CONNECTIONS", "2")),
            max_inactive_connection_lifetime=float(
                os.environ.get("POSTGRES_MAX_INACTIVE_CONNECTION_LIFETIME", "300")
            ),
        )
        self.connection_manager = ConnectionManager(config)
        self.serializer = JsonStorageSerializer()
        self.message_converter = MessageConverter()
        self.table_name = config.table_name

    async def delete(self, keys: List[str]):
        """Delete state from storage"""
        if not keys:
            return

        try:
            await self.connection_manager.ensure_connection()
            assert self.connection_manager.pool is not None
            async with self.connection_manager.pool.acquire() as conn:
                await conn.execute(
                    f"DELETE FROM {self.table_name} WHERE key = ANY($1::text[])", keys
                )
        except Exception as error:
            logger.error(f"PostgresStorage delete error: {str(error)}")
            raise

    async def read(self, keys: List[str]) -> Dict[str, Any]:
        """Read state from storage"""
        data = {}
        if not keys:
            return data

        try:
            await self.connection_manager.ensure_connection()
            assert self.connection_manager.pool is not None
            async with self.connection_manager.pool.acquire() as conn:
                rows = await conn.fetch(
                    f"SELECT key, data, e_tag FROM {self.table_name} WHERE key = ANY($1::text[])",
                    keys,
                )

                for row in rows:
                    item_data = jsonpickle.decode(row["data"])

                    if isinstance(item_data, dict):
                        item_data["e_tag"] = str(row["e_tag"])

                    # if item_data.get("chat_history"):
                    #     chat_history = item_data["chat_history"]
                    #     if isinstance(chat_history, list):
                    #         item_data["chat_history"] = [
                    #             self.message_converter.from_dict(msg)
                    #             if isinstance(msg, dict)
                    #             else msg
                    #             for msg in chat_history
                    #         ]

                    data[row["key"]] = item_data

        except Exception as error:
            logger.error(f"PostgresStorage read error: {str(error)}")
            raise

        return data

    async def write(self, changes: Dict[str, StoreItem]):
        """Write state to storage"""
        if changes is None:
            raise ValueError("Changes are required when writing")
        if not changes:
            return

        try:
            await self.connection_manager.ensure_connection()
            assert self.connection_manager.pool is not None
            async with self.connection_manager.pool.acquire() as conn:
                async with conn.transaction():
                    for key, change in changes.items():
                        await self._write_single_item(conn, key, change)

        except Exception as error:
            logger.error(f"PostgresStorage write error: {str(error)}")
            if "Etag conflict" in str(error):
                logger.warning(f"Handling ETag conflict: {str(error)}")
            else:
                raise

    async def _write_single_item(self, conn, key: str, change: StoreItem):
        """Write a single item to storage"""
        new_value = deepcopy(change)
        old_state_etag = None

        row = await conn.fetchrow(
            f"SELECT data, e_tag FROM {self.table_name} WHERE key = $1", key
        )

        if row:
            old_state_etag = str(row["e_tag"])
            new_value_etag = self._get_etag(new_value)

            if new_value_etag is None or new_value_etag == "*":
                logger.debug(f"postgresql_storage.write(): etag missing: {new_value}")

            if new_value_etag and self._has_etag_conflict(old_state_etag, new_value_etag):
                logger.warning(
                    f"ETag conflict: Original={new_value_etag}, Current={old_state_etag}"
                )

        new_etag = int(old_state_etag) + 1 if old_state_etag else 1
        self._set_etag(new_value, str(new_etag))

        # unpicklable=True is required to preserve the type of the object
        serializable_data = jsonpickle.encode(new_value, unpicklable=True)

        await conn.execute(
            f"""
            INSERT INTO {self.table_name} (key, data, e_tag, timestamp)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (key) 
            DO UPDATE SET data = $2, e_tag = $3, timestamp = CURRENT_TIMESTAMP
            """,
            key,
            serializable_data,
            new_etag,
        )

    def _get_etag(self, value: Any) -> Optional[str]:
        """Get e_tag from value"""
        logger.debug(f"postgresql_storage._get_etag(): value: {value}")
        if isinstance(value, dict):
            return value.get("e_tag")
        return getattr(value, "e_tag", None)

    def _set_etag(self, value: Any, etag: str):
        """Set e_tag in value"""
        if isinstance(value, dict):
            value["e_tag"] = etag
        else:
            value.e_tag = etag

    def _has_etag_conflict(self, old_etag: str, new_etag: str) -> bool:
        """Check for e_tag conflicts"""
        return (
            old_etag is not None
            and new_etag is not None
            and new_etag != "*"
            and new_etag != old_etag
        )

    def _prepare_serializable_data(self, value: Any) -> Dict:
        """Prepare data for serialization"""
        if isinstance(value, dict):
            serializable_data = {}
            for k, v in value.items():
                if k == "chat_history" and isinstance(v, list):
                    serializable_data[k] = [
                        (
                            self.message_converter.to_dict(msg)
                            if hasattr(msg, "role")
                            else msg
                        )
                        for msg in v
                    ]
                else:
                    serializable_data[k] = v

            return serializable_data

        if hasattr(value, "role"):
            return {
                **self.message_converter.to_dict(value),
                "e_tag": value.e_tag,
            }

        return value

    async def close(self):
        """Close the storage connection"""
        await self.connection_manager.close()


def is_json_serializable(value):
    try:
        json.dumps(value)
        return True
    except (TypeError, OverflowError):
        return False


def __sanitize_store_item(value):
    """
    Remove unserializable fields from StoreItem or dict recursively.
    """
    if isinstance(value, dict):
        return {
            k: __sanitize_store_item(v)
            for k, v in value.items()
            if is_json_serializable(v)
        }
    elif isinstance(value, StoreItem):
        clean_dict = {}
        for k, v in value.__dict__.items():
            if is_json_serializable(v):
                clean_dict[k] = v
            else:
                logger.warning(
                    f"Removed unserializable field '{k}' of type {type(v)} from StoreItem."
                )
        return clean_dict
    return value
