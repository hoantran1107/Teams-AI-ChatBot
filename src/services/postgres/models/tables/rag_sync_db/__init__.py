import datetime

from sqlalchemy import DateTime, TypeDecorator
from src.config.database_config import Base

# Import all models to ensure they are registered with SQLAlchemy
from .url_shortening_table import URLShortening

# Use the Base directly from database_config instead of creating a new one


class TZDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value and not value.tzinfo:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value
