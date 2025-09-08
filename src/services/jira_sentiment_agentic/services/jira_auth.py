from typing import Tuple
from src.config.settings import (
    atlassian_user,
    atlassian_api_token,
)


def get_jira_auth() -> Tuple[str, str]:
    """
    Get Jira authentication credentials from environment variables.

    Returns:
        A tuple of (email/username, API token) for basic authentication with Jira

    Raises:
        Exception: If required environment variables are not set
    """

    jira_email = atlassian_user
    jira_api_token = atlassian_api_token

    return (jira_email, jira_api_token)
