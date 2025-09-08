"""Bot configuration module.

Contains all bot-related configuration settings for Microsoft Teams.
"""

from src.config.database_config import db_config
from src.config.environment import env


class BotConfig:
    """Bot Configuration for Microsoft Teams."""

    APP_ID = env.get_str("BOT_ID", "")
    APP_PASSWORD = env.get_str("BOT_PASSWORD", "")
    APP_TENANT_ID = env.get_str("BOT_TENANT_ID", "")

    print(f"Running with bots credentials: app_id {APP_ID},app_password {APP_PASSWORD},app_tenant_id {APP_TENANT_ID}")

    POSTGRES_CONNECTION_STRING = env.get_str("POSTGRES_CONNECTION_STRING", db_config.database_url)
    # 10 Mean 5 turns
    MAX_HISTORY_MESSAGES = env.get_int("MAX_HISTORY_MESSAGES", 10)
