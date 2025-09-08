"""FastAPI configuration module.
Contains all FastAPI-related configuration and settings.
"""

from functools import lru_cache
from typing import Any, Dict

from pydantic import Field
from pydantic_settings import BaseSettings

from src.config.database_config import db_config
from src.config.environment import env


class DatabaseSettings(BaseSettings):
    """Database configuration settings for FastAPI"""

    user: str = Field(default_factory=lambda: db_config.user)
    password: str = Field(default_factory=lambda: db_config.password)
    host: str = Field(default_factory=lambda: db_config.host)
    port: str = Field(default_factory=lambda: db_config.port)
    name: str = Field(default_factory=lambda: db_config.name)
    vector_db_name: str = Field(default_factory=lambda: db_config.vector_db_name)

    # These properties are compatible with the existing code
    @property
    def database_url(self) -> str:
        return db_config.database_url

    @property
    def vector_db_url(self) -> str:
        return db_config.vector_db_url

    @property
    def vector_db_url_async(self) -> str:
        return db_config.vector_db_url_async

    @property
    def engine_options(self) -> Dict[str, Any]:
        return db_config.engine_options

    @property
    def database_ssl_context(self) -> Any:
        """Returns the SSL context for secure connections."""
        return db_config.db_ssl_context
    
    class Config:
        env_prefix = ""
        case_sensitive = False


class AppSettings(BaseSettings):
    """Application settings for FastAPI"""

    debug: bool = Field(default_factory=lambda: env.get_bool("DEBUG", False))
    testing: bool = Field(default_factory=lambda: env.get_bool("TESTING", False))
    app_port: int = Field(default_factory=lambda: env.get_int("APP_PORT", 5000))
    document_handler_domain: str = Field(default_factory=lambda: env.get_str("DOCUMENT_HANDLER_DOMAIN"))

    class Config:
        env_prefix = ""
        case_sensitive = False


class Settings(BaseSettings):
    """Main settings class that includes all sub-settings"""

    db: DatabaseSettings = Field(default_factory=lambda: DatabaseSettings())
    app: AppSettings = Field(default_factory=lambda: AppSettings())

    # API Documentation settings (FastAPI has built-in support for OpenAPI)
    api_title: str = "IFD CPB API"
    api_version: str = "v1"
    api_description: str = "FastAPI implementation of IFD Copilot API services"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from environment variables


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance to avoid reloading .env file on each request."""
    return Settings()


fastapi_settings = Settings()
