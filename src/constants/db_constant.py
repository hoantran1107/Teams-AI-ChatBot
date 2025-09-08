import psycopg

from src.config.database_config import DatabaseConfig

PG_CONN = psycopg.connect(
    conninfo=DatabaseConfig().database_url,
)
