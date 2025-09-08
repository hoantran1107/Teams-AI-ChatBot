import enum
from datetime import datetime
from typing import Self

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, scoped_session
from sqlalchemy.sql.sqltypes import DateTime

from src.config.database_config import Base, db
from src.config.database_config import db_session as default_session
from src.config.settings import atlassian_confluence_url
from src.services.postgres.models.tables.rag_sync_db import TZDateTime
from src.services.postgres.operation import DatabaseOperation


class SourceType(enum.Enum):
    """Source type enum."""

    GCP = "GCP"
    CONFLUENCE = "CONFLUENCE"


class Collection(Base, DatabaseOperation):
    """Collection model."""

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    run_cron_job: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=False, server_default=text("false")
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)  # Adding user_id field

    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uq_name_user_id"),
        {"extend_existing": True},
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "run_cron_job": self.run_cron_job,
            "note": self.note,
            "user_id": self.user_id,
        }

    @classmethod
    def get_by_name(cls, name: str, db_session: Session | None = None) -> list["Collection"]:
        return cls.find_by_filter(name=name, db_session=db_session)

    @classmethod
    def get_cron_job_collections(cls, db_session: scoped_session[Session] | None = None) -> list[Self]:
        db_session = db_session or default_session
        return db_session.query(cls).filter_by(run_cron_job=True).all()

    @classmethod
    def get_sources_has_note(
        cls,
        sources: list[str],
        db_session: scoped_session[Session] | None = None,
    ) -> list["Collection"]:
        db_session = db_session or default_session
        collections = db_session.query(cls).filter(cls.name.in_(sources), cls.note.isnot(None)).all()  # type: ignore

        return collections

    @classmethod
    def get_by_user_id(cls, user_id: str, db_session: scoped_session[Session] | None = None) -> list[str]:
        db_session = db_session or default_session
        collections = db_session.query(cls).filter_by(user_id=user_id).all()

        return [collection.name for collection in collections]

    @classmethod
    def get_common_sources_has_note(cls, db_session: Session | None = None) -> list["Collection"]:
        db_session = db_session or default_session  # type: ignore
        return db_session.query(cls).filter(cls.note.isnot(None), cls.user_id.is_(None)).all()  # type: ignore


class SyncLog(Base, DatabaseOperation):
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("collections.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType), server_default=text("'CONFLUENCE'"), nullable=False
    )
    source_path: Mapped[str] = mapped_column(String, server_default="https://infodation.atlassian.net/wiki")
    last_sync_time: Mapped[datetime] = mapped_column(TZDateTime, default=func.current_timestamp())
    documents_added: Mapped[int] = mapped_column(Integer, default=0)
    documents_updated: Mapped[int] = mapped_column(Integer, default=0)
    documents_deleted: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_sync_log_collection_id", "collection_id"),
        {"extend_existing": True},  # Add extend_existing=True to avoid redefinition errors
    )

    @classmethod
    def get_minute_range_latest_update(
        cls,
        collection_id: int,
        source_type: SourceType,
        source_path: str,
        db_session: scoped_session[Session] | None = None,
    ) -> int | None:
        """Get the number of minutes since the last sync."""
        db_session = db_session or default_session

        # Use the new style SQLAlchemy 2.0 select
        minutes_expr = func.ceil(func.extract("epoch", func.now() - cls.last_sync_time) / 60).label("minutes")

        query = (
            select(minutes_expr)
            .where(
                cls.collection_id == collection_id,
                cls.source_type == source_type,
                cls.source_path == source_path,
            )
            .order_by(cls.id.desc())
            .limit(1)
        )
        result = db_session.execute(query).scalar()
        return int(result) if result else None


class DocumentLog(Base, DatabaseOperation):
    """Document log model."""

    __tablename__ = "document_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identity_constant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    url_download: Mapped[str | None] = mapped_column(String(255))
    created_date: Mapped[datetime] = mapped_column(TZDateTime, default=func.now())
    updated_date: Mapped[datetime] = mapped_column(TZDateTime, default=func.now(), onupdate=func.now())
    source_created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_version: Mapped[str | None] = mapped_column(String, nullable=True)
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("collections.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=True,
    )
    data_source_metadata: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType), nullable=False, server_default=text("'CONFLUENCE'")
    )
    source_path: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text(f"'{atlassian_confluence_url}'")
    )
    is_new_doc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint(
            "identity_constant_name",
            "collection_id",
            "source_type",
            name="unique_document_collection_source",
        ),
        Index("idx_document_log_collection_id", "collection_id"),
        Index("idx_document_source", "source_type", "source_path"),
        Index("idx_data_source_metadata", "data_source_metadata", postgresql_using="gin"),
        {"extend_existing": True},  # Add extend_existing=True to avoid redefinition errors
    )

    @classmethod
    def get_non_updatable_columns(cls) -> list[str]:
        return [
            cls.id.name,
            cls.identity_constant_name.name,
            cls.created_date.name,
            cls.data_source_metadata,
        ]

    @classmethod
    def get_by_collection_id(
        cls, collection_id: int, db_session: scoped_session[Session] | None = None
    ) -> list["DocumentLog"]:
        return cls.find_by_filter(collection_id=collection_id, db_session=db_session)

    @classmethod
    def delete_by_names_and_collection_id(
        cls, names: list[str], collection_id: int, db_session: Session | None = None
    ) -> None:
        db_session = db_session or default_session
        db_session.query(cls).filter(cls.identity_constant_name.in_(names), cls.collection_id == collection_id).delete(
            synchronize_session=False
        )
        db_session.commit()

    @classmethod
    def get_by_collection_and_source(
        cls,
        collection_id: int,
        source_type: SourceType,
        source_path: str,
        db_session: Session | None = None,
    ) -> list["DocumentLog"]:
        db_session = db_session or default_session
        return (
            db.session.query(cls)
            .filter_by(
                collection_id=collection_id,
                source_type=source_type,
                source_path=source_path,
            )
            .all()
        )

    @classmethod
    def get_existing_pages(
        cls,
        collection_id: int,
        source_type: SourceType,
        page_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        """Get the list of page IDs that exist for a collection.

        Args:
            collection_id: ID of the collection
            source_type: Type of the source (e.g., GCP, Confluence)
            page_ids: List of page IDs to check

        Returns:
            A tuple containing (existing_page_ids, not_found_page_ids)

        """
        results = cls.find_by_filter(collection_id=collection_id, source_type=source_type)
        existing_page_ids = [row.identity_constant_name for row in results if row.identity_constant_name in page_ids]
        not_found_page_ids = list(set(page_ids) - set(existing_page_ids))
        return existing_page_ids, not_found_page_ids

    @classmethod
    def delete_pages(cls, collection_id: int, identity_constant_name: list[str]):
        """Delete pages from a collection by page IDs.

        Args:
            collection_id: ID of the collection
            identity_constant_name: List of page IDs to delete

        """
        if not identity_constant_name:
            return

        db.session.query(cls).filter(
            cls.collection_id == collection_id,
            cls.identity_constant_name.in_(identity_constant_name),
        ).delete(synchronize_session=False)
        db.session.commit()
