from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import Column, func, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from src.config.database_config import Base, db
from src.services.postgres.models.tables.rag_sync_db import TZDateTime
from src.services.postgres.operation import DatabaseOperation


@dataclass
class StoreItem:
	"""
	A data class representing a stored item in the database.

	Attributes:
		namespace (str): The namespace of the item.
		key (str): The unique key identifying the item.
		value (Dict[str, Any]): The value associated with the key, stored as a dictionary.
		created_at (datetime): The timestamp when the item was created.
		updated_at (datetime): The timestamp when the item was last updated.
	"""
	namespace: str
	key: str
	value: Dict[str, Any]
	created_at: datetime
	updated_at: datetime


class ConversationInstructions(Base, DatabaseOperation):
	"""
	A SQLAlchemy model representing the 'conversation_instructions' table.

	Attributes:
		id (int): The primary key of the table.
		namespace (str): The namespace of the instruction, indexed for faster lookups.
		key (str): The unique key identifying the instruction, indexed for faster lookups.
		value (dict): The JSONB value associated with the instruction.
		created_at (datetime): The timestamp when the record was created.
		updated_at (datetime): The timestamp when the record was last updated.
	"""

	__tablename__ = 'conversation_instructions'

	id = Column(Integer, primary_key=True)
	namespace = Column(Text, nullable=False, index=True)  # Index for namespace
	key = Column(String(255), nullable=False, index=True)  # Index for key
	value = Column(JSONB, nullable=False)
	created_at = Column(TZDateTime, server_default=func.now())
	updated_at = Column(
		TZDateTime, server_default=func.now(),
		onupdate=func.now()
	)

	__table_args__ = (
		UniqueConstraint('namespace', 'key', name='uq_namespace_instruction'),
		Index('idx_namespace_instruction', 'namespace', 'key'),
		Index('idx_instruction_value_gin', 'value', postgresql_using='gin'),
	)

	@staticmethod
	def _serialize_namespace(namespace: Tuple[str, ...]) -> str:
		"""
		Convert a tuple namespace into a string for storage in the database.

		Args:
			namespace (Tuple[str, ...]): The namespace as a tuple of strings.

		Returns:
			str: The namespace as a dot-separated string.
		"""
		if isinstance(namespace, tuple):
			return ".".join(namespace)
		return str(namespace)

	@classmethod
	def get(cls, namespace: Tuple[str, ...], key: str) -> Optional[StoreItem]:
		"""
		Retrieve a record from the database based on namespace and key.

		Args:
			namespace (Tuple[str, ...]): The namespace of the record as a tuple.
			key (str): The unique key of the record.

		Returns:
			Optional[StoreItem]: A `StoreItem` object if the record exists, otherwise None.
		"""
		namespace_str = cls._serialize_namespace(namespace)

		record = db.session.query(cls).filter_by(
			namespace=namespace_str, key=key
		).first()

		if record:
			return StoreItem(
				namespace=namespace_str,
				key=record.key,
				value=record.value,
				created_at=record.created_at,
				updated_at=record.updated_at
			)
		return None

	@classmethod
	def put(cls: Any, namespace: Tuple[str, ...], key: str, value: Dict[str, Any]) -> None:
		"""
		Insert or update a record in the database.

		Args:
			namespace (Tuple[str, ...]): The namespace of the record as a tuple.
			key (str): The unique key of the record.
			value (Dict[str, Any]): The value to be stored as a dictionary.

		Returns:
			None
		"""
		namespace_str = cls._serialize_namespace(namespace)

		# Check if the record already exists
		existing = db.session.query(cls).filter_by(
			namespace=namespace_str,
			key=key
		).first()

		if existing:
			existing.value = value
		else:
			record = cls(namespace=namespace_str, key=key, value=value)
			db.session.add(record)

		db.session.commit()
