from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB  # Import PostgreSQL specific types

from src.config.database_config import Base
from src.services.postgres.operation import DatabaseOperation


class ChatHistory(Base, DatabaseOperation):
    """
    SQLAlchemy model for chat history.
    Stores chat messages for conversations.
    """
    __tablename__ = 'chat_history'

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(100), index=True)
    user_name = Column(String(100))
    message = Column(JSON().with_variant(JSONB, 'postgresql'), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default='CURRENT_TIMESTAMP'
    )

    # Define composite indexes
    __table_args__ = (
        # Index for created_at with descending order for latest-first queries
        Index('idx_chat_history_created_at', created_at.desc()),
        # Combined index on session_id and created_at for efficiently retrieving a session's history
        Index('idx_chat_history_session_time', session_id, created_at.desc()),
    )

    @classmethod
    def get_history_by_session(cls, session_id, limit=50, db_session=None):
        """Get chat history for a specific session, sorted by created_at descending"""
        return cls.find_by_filter(session_id=session_id, db_session=db_session)[:limit]
