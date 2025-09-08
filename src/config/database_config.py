"""Database configuration module.

Contains all database-related configuration settings.
"""

import logging
import urllib.parse
from collections.abc import Generator
from contextlib import contextmanager
from ssl import CERT_NONE, create_default_context
from ssl import Purpose as SSLPurpose
from tempfile import _TemporaryFileWrapper

from sqlalchemy import Engine, create_engine, func, text
from sqlalchemy.orm import Session, declarative_base, scoped_session, sessionmaker

from src.config.environment import env

_logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration settings."""

    # Core PostgreSQL connection details
    user = env.get_str("DB_USER", "postgres")
    password = env.get_str("DB_PASSWORD", "")
    host = env.get_str("DB_HOST", "localhost")
    port = env.get_str("DB_PORT", "5432")
    name = env.get_str("DB_NAME", "rag_sync")
    postgresql_client_cert: str = env.get_str(key="POSTGRESQL_CLIENT_CERT")
    postgresql_client_key: str = env.get_str(key="POSTGRESQL_CLIENT_KEY")
    postgresql_ca_cert: str = env.get_str(key="POSTGRESQL_CA_CERT")
    ssl_context = None
    # Additional databases
    vector_db_name = env.get_str("VECTOR_DB_NAME", "documents_vector")
    autotest_db_name = env.get_str("DB_NAME_AUTOTEST", "autotest_rag")

    # SQLAlchemy engine options
    pool_size = 100
    max_overflow = 115
    pool_timeout = 30
    pool_recycle = 1800
    pool_pre_ping = True

    @property
    def encoded_password(self) -> str:
        """Get URL encoded password for use in connection strings."""
        if not self.password:
            msg = "DB Password is not set"
            raise ValueError(msg)
        return urllib.parse.quote_plus(self.password)

    @property
    def database_url(self) -> str:
        """Returns the database URL with encoded password."""
        if self.postgresql_client_cert and self.postgresql_client_key and self.postgresql_ca_cert:
            return self.database_url_with_ssl
        return f"postgresql://{self.user}:{self.encoded_password}@{self.host}:{self.port}/{self.name}"

    @property
    def database_url_with_ssl(self) -> str:
        """Returns the ssl database URL with encoded password."""
        self.get_db_cert_on_gcp()
        return f"postgresql://{self.user}:{self.encoded_password}@{self.host}:{self.port}/{self.name}?sslmode=require&sslrootcert={self.postgresql_ca_cert}&sslcert={self.postgresql_client_cert}&sslkey={self.postgresql_client_key}"

    @property
    def vector_db_url(self) -> str:
        """Returns the vector database URL with encoded password."""
        if self.postgresql_client_cert and self.postgresql_client_key and self.postgresql_ca_cert:
            return self.vector_db_url_with_ssl
        return f"postgresql://{self.user}:{self.encoded_password}@{self.host}:{self.port}/{self.vector_db_name}"

    @property
    def vector_db_url_with_ssl(self) -> str:
        """Returns the ssl vector database URL with encoded password."""
        self.get_db_cert_on_gcp()
        return f"postgresql://{self.user}:{self.encoded_password}@{self.host}:{self.port}/{self.vector_db_name}?sslmode=require&sslrootcert={self.postgresql_ca_cert}&sslcert={self.postgresql_client_cert}&sslkey={self.postgresql_client_key}"

    @property
    def vector_db_url_async(self) -> str:
        """Returns the async vector database URL with encoded password."""
        return f"postgresql+asyncpg://{self.user}:{self.encoded_password}@{self.host}:{self.port}/{self.vector_db_name}"

    @property
    def db_ssl_context(self):
        """Returns the SSL context for secure connections."""
        if not self.postgresql_ca_cert and not self.postgresql_client_cert and not self.postgresql_client_key:
            return None
        if not self.ssl_context:
            self.get_db_cert_on_gcp()
            self.ssl_context = create_default_context(
                purpose=SSLPurpose.SERVER_AUTH,
                cafile=self.postgresql_ca_cert,
            )
            self.ssl_context.load_cert_chain(
                certfile=self.postgresql_client_cert,
                keyfile=self.postgresql_client_key,
            )
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = CERT_NONE
            return self.ssl_context

    @property
    def autotest_db_url(self) -> str:
        """Returns the autotest database URL with encoded password."""
        return f"postgresql://{self.user}:{self.encoded_password}@{self.host}:{self.port}/{self.autotest_db_name}"

    @property
    def engine_options(self) -> dict:
        """Returns SQLAlchemy engine options."""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
        }

    def get_db_cert_on_gcp(self):
        """Get database SSL certificates on Google Cloud Platform."""
        from os import getenv
        from tempfile import NamedTemporaryFile

        def write_to_temp_file(content: str) -> str:
            f: _TemporaryFileWrapper[str] = NamedTemporaryFile(
                delete=False,
                mode="w",
                suffix=".pem",
            )
            f.write(content)
            f.close()
            return f.name

        # K_SERVICE is the name of the Cloud Run service
        if getenv(key="K_SERVICE"):
            if not self.postgresql_client_cert.endswith(".pem"):
                self.postgresql_client_cert = write_to_temp_file(
                    content=self.postgresql_client_cert,
                )
            if not self.postgresql_client_key.endswith(".pem"):
                self.postgresql_client_key = write_to_temp_file(
                    content=self.postgresql_client_key,
                )
            if not self.postgresql_ca_cert.endswith(".pem"):
                self.postgresql_ca_cert = write_to_temp_file(
                    content=self.postgresql_ca_cert,
                )


# Create singleton instance
db_config = DatabaseConfig()
engine: Engine | None = None
gcloud_project_id = env.get_str(key="GCLOUD_PROJECT_ID")
schema_list = ["ifd_rag_data", "public"]
search_path = ",".join(schema_list)
# Create SQLAlchemy engine and session
engine: Engine = create_engine(
    url=db_config.database_url,
    connect_args={"options": f"-c search_path={search_path}"},
    **db_config.engine_options,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
db_session = scoped_session(session_factory=SessionLocal)
Base = declarative_base()
Base.query = db_session.query_property()


# FastAPI dependency for DB sessions
def get_db() -> Generator[Session]:
    """FastAPI dependency that provides a database session.

    Usage:
    @app.get("/endpoint")
    def endpoint(db: Session = Depends(get_db)):
        # Use db here.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session]:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Modern database interface with SQLAlchemy query helpers
class DatabaseInterface:
    """Modern database interface for SQLAlchemy operations."""

    def __init__(self, engine, session_factory):
        """Initialize the database interface with engine and session factory."""
        self.engine = engine
        self.session_factory = session_factory
        self.session = session_factory()  # Scoped session for compatibility
        self.base_model = Base
        # SQL helper functions
        self.func = func
        self.text = text

    def create_session(self) -> Session:
        """Create a new session."""
        return self.session_factory()

    def create_scoped_session(self):
        """Create a new scoped session for backwards compatibility."""
        return scoped_session(self.session_factory)

    @contextmanager
    def session_context(self):
        """Context manager for using sessions."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def query(self, *entities):
        """Query helper that works with the current session."""
        return self.session.query(*entities)


# Create new db object that replaces the legacy interface
db = DatabaseInterface(engine, SessionLocal)


# Legacy database interface for backwards compatibility
class LegacyDatabaseInterface(DatabaseInterface):
    """Legacy database interface for backwards compatibility with existing code."""


def init_db() -> None:
    """Initialize all database tables."""
    # Import all models here to ensure they're registered with Base metadata

    # RAG sync database models

    # Vector database models

    # Create all tables
    Base.metadata.create_all(bind=engine)
