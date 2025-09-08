from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint, Index, func
from sqlalchemy.sql.expression import text

from src.config.database_config import Base
from src.services.postgres.operation import DatabaseOperation


class URLShortening(Base, DatabaseOperation):
    """
    URLShortening model for storing URL mapping for citation shortening
    """
    __tablename__ = 'url_shortening'

    id = Column(Integer, primary_key=True, autoincrement=True)
    short_code = Column(String(8), nullable=False, unique=True)
    original_url = Column(Text, nullable=False)
    display_url = Column(String(100), nullable=False)  # Shortened display version
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_accessed = Column(DateTime(timezone=True), nullable=True)
    access_count = Column(Integer, server_default=text('0'), nullable=False)

    __table_args__ = (
        UniqueConstraint('short_code', name='uq_url_short_code'),
        UniqueConstraint('original_url', name='uq_url_original_url'),
        Index('idx_url_short_code', 'short_code', unique=True),
        Index('idx_url_original_url', 'original_url'),
        Index('idx_url_created_at', 'created_at'),
        {'extend_existing': True}
    )

    @classmethod
    def get_by_short_code(cls, short_code: str, db_session=None) -> Optional['URLShortening']:
        """Get URL mapping by short code"""
        results = cls.find_by_filter(short_code=short_code, db_session=db_session)
        return results[0] if results else None

    @classmethod
    def get_by_original_url(cls, original_url: str, db_session=None) -> Optional['URLShortening']:
        """Get URL mapping by original URL"""
        results = cls.find_by_filter(original_url=original_url, db_session=db_session)
        return results[0] if results else None

    @classmethod
    def create_or_get_mapping(cls, original_url: str, display_url: str, db_session=None) -> 'URLShortening':
        """Create new mapping or return existing one"""
        # Check if mapping already exists
        existing = cls.get_by_original_url(original_url, db_session)
        if existing:
            return existing
        
        # Generate unique short code
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        
        short_code = None
        max_attempts = 100
        for _ in range(max_attempts):
            candidate = ''.join(secrets.choice(alphabet) for _ in range(6))
            if not cls.get_by_short_code(candidate, db_session):
                short_code = candidate
                break
        
        if not short_code:
            raise RuntimeError("Unable to generate unique short code")
        
        # Create new mapping
        new_mapping = cls(
            short_code=short_code,
            original_url=original_url,
            display_url=display_url
        )
        new_mapping.save(db_session=db_session)
        return new_mapping

    def record_access(self, db_session=None):
        """Record access to this shortened URL"""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1
        self.save(db_session=db_session)
