import json
import logging
import os

from dotenv import load_dotenv
from tavily import TavilyClient

# Load environment variables once at module level
load_dotenv()

logger = logging.getLogger(__name__)

EMPTY_QUERY_MSG = "Empty search query provided"

# Singleton instance of TavilyClient
_tavily_client_instance = None


def get_tavily_client() -> TavilyClient | None:
    """Get a singleton instance of TavilyClient with the API key from environment variables.

    Returns:
        TavilyClient instance or None if API key is not set

    """
    global _tavily_client_instance  # noqa: PLW0603, use global instance because the Tavily API limits the number of client instances to only two, and sharing a single instance ensures compliance with this restriction.

    if _tavily_client_instance is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if api_key:
            _tavily_client_instance = TavilyClient(api_key=api_key)

    return _tavily_client_instance


async def search_with_tavily(query: str) -> str:
    """Perform a search using Tavily API."""
    if not query or not query.strip():
        logger.warning(EMPTY_QUERY_MSG)
        return "The search query is empty."

    tavily_client = get_tavily_client()
    if not tavily_client or not tavily_client.api_key:
        logger.error("Tavily API key is not set.")
        return "Tavily API key is not set."

    try:
        response = tavily_client.search(query=query, include_answer="advanced")
        return json.dumps(response)
    except Exception as e:
        logger.exception("Error performing search")
        raise
