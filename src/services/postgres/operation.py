import functools
from typing import Any, Self, TypeVar

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.config.database_config import db

T = TypeVar("T", bound="DatabaseOperation", covariant=True)


def transaction_handler(func):
    """Handle transaction management and automatic rollback on failure."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extract session from kwargs or use default
        db_session = kwargs.get("db_session")
        if db_session is None:
            for arg in args:
                if isinstance(arg, Session):
                    db_session = arg
                    break
            db_session = db_session or db.session

        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            db_session.rollback()
            raise e

    return wrapper


class DatabaseOperation:
    """Base class for database operations."""

    @classmethod
    @transaction_handler
    def create(cls, db_session: Session | None = None, **kwargs) -> Self:
        """Create a new instance in the database.

        Args:
            db_session: SQLAlchemy session to use
            **kwargs: Fields to set on the model

        Returns:
            The created instance

        """
        session = db_session or db.session
        instance = cls(**kwargs)
        session.add(instance)
        session.commit()
        return instance

    @classmethod
    @transaction_handler
    def check_exists_by_id(cls, db_session: Session | None = None, id: int | None = None) -> bool:
        """Check if an instance exists by ID.

        Args:
            db_session: SQLAlchemy session to use
            id: ID of the instance to check

        Returns:
            True if the instance exists, False otherwise

        """
        session = db_session or db.session
        query = session.query(cls).filter_by(id=id).exists()
        return session.query(query).scalar()

    @classmethod
    @transaction_handler
    def find_by_filter(cls, db_session: Session | None = None, **kwargs) -> list[T]:
        """Find instances by filters using Django-style lookups.

        Args:
            db_session: SQLAlchemy session to use
            **kwargs: Filter conditions with Django-style lookups (field__operator=value)

        Returns:
            List of matching instances

        """
        session = db_session or db.session
        if session is None:
            msg = "Session is required"
            raise ValueError(msg)

        query = session.query(cls)

        # Process kwargs to extract special lookups
        for key, value in list(kwargs.items()):
            if "__" in key:
                field_name, lookup_type = key.split("__", 1)
                kwargs.pop(key)  # Remove the special lookup from kwargs

                # Get the model attribute for this field
                field = getattr(cls, field_name, None)
                if field is None:
                    raise ValueError(f"Field '{field_name}' not found in model {cls.__name__}")

                # Handle the lookup types
                if lookup_type == "in":
                    query = query.filter(field.in_(value))
                elif lookup_type == "gt":
                    query = query.filter(field > value)
                elif lookup_type == "lt":
                    query = query.filter(field < value)
                elif lookup_type == "gte":
                    query = query.filter(field >= value)
                elif lookup_type == "lte":
                    query = query.filter(field <= value)
                elif lookup_type == "contains":
                    query = query.filter(field.contains(value))
                elif lookup_type == "icontains":
                    query = query.filter(field.ilike(f"%{value}%"))
                elif lookup_type == "startswith":
                    query = query.filter(field.startswith(value))
                elif lookup_type == "endswith":
                    query = query.filter(field.endswith(value))
                elif lookup_type == "isnull":
                    if value:
                        query = query.filter(field.is_(None))
                    else:
                        query = query.filter(field.isnot(None))
                elif lookup_type == "exact":
                    query = query.filter(field == value)
                else:
                    raise ValueError(f"Unsupported lookup type: {lookup_type}")

        # Apply remaining kwargs as exact matches
        if kwargs:
            query = query.filter_by(**kwargs)

        return query.all()

    @classmethod
    @transaction_handler
    def find_all(cls, db_session: Session | None = None, limit: int | None = None) -> list[T]:
        """Find all instances of this model.

        Args:
            db_session: SQLAlchemy session to use
            limit: Optional limit on the number of results

        Returns:
            List of all instances

        """
        session = db_session or db.session
        query = session.query(cls)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @classmethod
    @transaction_handler
    def delete_by_filter(cls, db_session: Session | None = None, **kwargs) -> None:
        """Delete instances matching filters.

        Args:
            db_session: SQLAlchemy session to use
            **kwargs: Filter conditions

        """
        session = db_session or db.session
        session.query(cls).filter_by(**kwargs).delete()
        session.commit()

    @classmethod
    @transaction_handler
    def upsert(cls, keys: list[str], db_session: Session | None = None, **values) -> dict[str, Any]:
        """Upsert values into the database using PostgreSQL's INSERT ... ON CONFLICT.

        Args:
            keys: List of column names to use as the conflict target
            db_session: SQLAlchemy session to use
            **values: Column values to insert/update

        Returns:
            Dictionary of inserted/updated values

        """
        session = db_session or db.session

        stmt = insert(cls.__table__).values(**values)
        update_values = {k: v for k, v in values.items() if k not in keys}

        if update_values:
            stmt = stmt.on_conflict_do_update(index_elements=keys, set_=update_values)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=keys)

        session.execute(stmt)
        session.commit()

        return values

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)

            # Handle datetime objects
            if hasattr(value, "isoformat"):
                value = value.isoformat()

            result[column.name] = value
        return result

    @transaction_handler
    def save(self, db_session: Session | None = None) -> None:
        """Save this instance to the database.

        Args:
            db_session: SQLAlchemy session to use

        """
        session = db_session or db.session
        session.add(self)
        session.commit()

    @transaction_handler
    def delete(self, db_session: Session | None = None) -> None:
        """Delete this instance from the database.

        Args:
            db_session: SQLAlchemy session to use

        """
        session = db_session or db.session
        session.delete(self)
        session.commit()

    @transaction_handler
    def bulk_insert(self, data: list[dict[str, Any]], db_session: Session | None = None) -> None:
        """Bulk insert data into the database.

        Args:
            data: List of dictionaries to insert
            db_session: SQLAlchemy session to use

        """
        session = db_session or db.session
        session.bulk_insert_mappings(self.__class__, data)
        session.commit()
