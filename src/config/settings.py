"""Main settings module for the application.

This is a centralized module that imports and re-exports settings from other config modules.

Legacy applications can continue to import from this module.
"""

import os

from src.config.ai_config import ai_config
from src.config.database_config import db_config
from src.config.environment import env
from src.config.fastapi_config import fastapi_settings

# Re-export SQLAlchemy configuration for FastAPI
SQLALCHEMY_DATABASE_URI = fastapi_settings.db.database_url

# Keep these variables accessible directly from settings module for compatibility
# Azure OpenAI API configuration
api_key = ai_config.azure.api_key
azure_openai_endpoint = ai_config.azure.azure_openai_endpoint
azure_chat_deployment_name = ai_config.azure.azure_openai_model_deployment_name
azure_chat_api_version = ai_config.azure.chat_api_version
azure_embedding_api_version = ai_config.azure.embedding_api_version
azure_embedding_deployment_name = ai_config.azure.azure_embedding_model
embedding_deployment = ai_config.azure.embedding_deployment
app_port = fastapi_settings.app.app_port
# Google Cloud Platform configuration
google_application_credentials = env.get_str("GOOGLE_APPLICATION_CREDENTIALS")
redis_host = env.get_str("REDIS_HOST")
gcp_bucket_name = env.get_str("GCP_BUCKET_NAME")
gcp_project_name = env.get_str("GCP_PROJECT_NAME")

# Legacy PostgreSQL configuration (kept for compatibility)
postgres_db_user = db_config.user
postgres_db_password = db_config.password
postgres_db_host = db_config.host
postgres_db_port = db_config.port
postgres_db_name_autotest = db_config.autotest_db_name

# Atlassian configuration
atlassian_base_url = env.get_str("ATLASSIAN_BASE_URL", "https://infodation.atlassian.net")
atlassian_jira_url = atlassian_base_url
atlassian_confluence_url = f"{atlassian_base_url}/wiki"
atlassian_user = env.get_str("ATLASSIAN_USER")
atlassian_api_token = env.get_str("ATLASSIAN_API_TOKEN")

# Only generate document sprint for project IFDCPB
enable_generate_sprint_for_ifdcpb = env.get_str("ENABLE_GENERATE_SPRINT_FOR_IFDCPB")
# This using for when click on citation link in chat response it will call the redirect_short_url endpoint to redirect to the original Atlassian url
# /redirect/{short_code}
url_shortening_domain = env.get_str("URL_SHORTENING_DOMAIN")

docling_serve_url = env.get_str("DOCLING_SERVE_URL")
if not docling_serve_url:
    raise ValueError("DOCLING_SERVE_URL is not set")

n8n_webhook_url = env.get_str("N8N_MCP_URL")

webhook_auth_username = env.get_str("ATLASSIAN_USER")
webhook_auth_password = env.get_str("ATLASSIAN_API_TOKEN")
