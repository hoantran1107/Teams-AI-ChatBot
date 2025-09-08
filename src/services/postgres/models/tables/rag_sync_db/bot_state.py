from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, Index, func

from src.config.database_config import Base
from src.services.postgres.operation import DatabaseOperation


class BotState(Base, DatabaseOperation):
    """
    SQLAlchemy model for the bot_state table used by PostgresStorage.
    This table stores the state information for bot conversations.
    """

    __tablename__ = "bot_state"

    key = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)
    e_tag = Column(Integer, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
    )

    # Define indexes using __table_args__
    __table_args__ = (
        # Index for timestamp-based queries with descending order (matches async implementation)
        Index(f"idx_{__tablename__}_timestamp", timestamp.desc()),
    )
