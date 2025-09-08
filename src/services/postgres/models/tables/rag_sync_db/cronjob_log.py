import logging
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    func,
    select,
    true,
)
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.orm.scoping import scoped_session

from src.config.database_config import Base
from src.config.database_config import db_session as default_session
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import Collection
from src.services.postgres.operation import DatabaseOperation

_logger = logging.getLogger(__name__)


class CronJobLog(Base, DatabaseOperation):
    """Table is used to log the cronjob execution."""

    __tablename__ = "cronjob_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_processing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=True)
    log: Mapped[str] = mapped_column(String, nullable=True)
    updated_rag_sources: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("idx_updated_rag_sources", updated_rag_sources, postgresql_using="gin"),)

    @classmethod
    def get_latest_log(cls, db_session: scoped_session[Session] | None = None) -> "CronJobLog | None":
        """Get the latest log."""
        db_session = db_session or default_session
        return db_session.query(cls).order_by(cls.id.desc()).first()

    @classmethod
    def get_latest_success_log(cls, db_session: scoped_session[Session] | None = None) -> "CronJobLog | None":
        """Get the latest success log."""
        db_session = db_session or default_session
        return db_session.query(cls).filter_by(is_success=True).order_by(cls.id.desc()).first()

    @classmethod
    def create_new_log(
        cls,
        sources: list[Collection],
        is_processing=True,
        is_success=None,
        log=None,
        end_time=None,
        db_session: Session | None = None,
    ) -> int:
        """Create a new log."""
        new_log = cls.create(
            updated_rag_sources=[
                source.name if source.user_id is None else f"{source.name}_({source.user_id})" for source in sources
            ],
            is_processing=is_processing,
            is_success=is_success,
            log=log,
            end_time=end_time,
            db_session=db_session,
        )
        return new_log.id

    @classmethod
    def update_log(
        cls,
        log_id,
        is_processing=None,
        is_success=None,
        log=None,
        end_time=None,
        db_session: Session | None = None,
    ) -> None:
        """Update a log by id."""
        cls.update_by_id(
            log_id,
            is_processing=is_processing,
            is_success=is_success,
            log=log,
            end_time=end_time,
            db_session=db_session,
        )

    @classmethod
    def update_by_id(
        cls,
        log_id,
        is_processing=None,
        is_success=None,
        log=None,
        end_time=None,
        db_session: scoped_session[Session] | None = None,
    ) -> None:
        """Update a log by id."""
        db_session = db_session or default_session
        log_entry = db_session.query(cls).filter_by(id=log_id).first()
        if not log_entry:
            raise ValueError(f"Cant find this collection with id {log_id}")

        if is_processing is not None:
            log_entry.is_processing = is_processing
        if is_success is not None:
            log_entry.is_success = is_success
        if log is not None:
            log_entry.log = log
        if end_time is not None:
            log_entry.end_time = end_time

        db_session.commit()

    @classmethod
    def get_minute_range_latest_update(
        cls,
        collection_name=None,
        collection_id=None,
        db_session: scoped_session[Session] | None = None,
    ) -> int | None:
        """Get the minute range of the latest update."""
        db_session = db_session or default_session

        # If collection_id is provided, get the collection to find its name
        if collection_id:
            collection = db_session.query(Collection).filter_by(id=collection_id).first()
            if not collection:
                _logger.error("Cant find this collection with id %s", collection_id)
                return None

            collection_name = collection.name

        # Use the new style SQLAlchemy 2.0 select
        minutes_expr = func.ceil(func.extract("epoch", func.now() - cls.end_time) / 60).label("minutes")
        query = (
            select(minutes_expr)
            .where(cls.updated_rag_sources.any(collection_name), cls.is_success == true())
            .order_by(cls.id.desc())
            .limit(1)
        )

        result = db_session.execute(query).scalar()
        return int(result) if result else None
