import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.config.settings import (
    n8n_webhook_url,
    webhook_auth_password,
    webhook_auth_username,
)
from src.services.jira_services.services.jira_utils import extract_context_data
from src.services.n8n_services.services.exceptions import (
    N8NConfigurationError,
    N8NConnectionError,
)

_logger = logging.getLogger(__name__)
HTTP_OK = 200


def _validate_n8n_configuration() -> str:
    """Check config and enforce HTTPS."""
    if not n8n_webhook_url or not isinstance(n8n_webhook_url, str):
        msg = "N8N webhook URL is not configured or invalid"
        raise N8NConfigurationError(msg)

    url = n8n_webhook_url.strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        msg = "N8N webhook URL must use HTTPS"
        raise N8NConfigurationError(msg)

    if not webhook_auth_username or not webhook_auth_password:
        _logger.warning(
            "N8N auth credentials not configured, request will be unauthenticated"
        )

    return url


def _get_user_query(context: TurnContext) -> str:
    """Try extract query; fallback to text; default 'help'."""
    try:
        extracted = extract_context_data(context, ["query"])
        if extracted and isinstance(extracted[0], str):
            return extracted[0].strip()
    except Exception as e:
        _logger.error("Failed to extract query: %s", type(e).__name__)

    text = getattr(getattr(context, "activity", None), "text", None)
    if text and text.strip():
        return text.strip()

    return "help"


def _prepare_payload(query: str, state: AppTurnState) -> dict[str, Any]:
    """Prepare payload for N8N webhook request."""
    session_id = (
        state.conversation.get("session_id", "bot-ai-session")
        if state
        else "bot-ai-session"
    )
    return {
        "action": "sendMessage",
        "sessionId": session_id,
        "chatInput": query or "help",
    }


def _process_response(response: httpx.Response) -> str:
    """Normalize response."""
    if response.status_code != HTTP_OK:
        return f"N8N service error (HTTP {response.status_code})."

    try:
        data = response.json()
        if isinstance(data, dict):
            for key in (
                "output",
                "response",
                "result",
                "message",
                "answer",
                "text",
                "content",
            ):
                val = str(data.get(key, "")).strip()
                if val:
                    return val
    except Exception:
        _logger.warning("N8N response is not JSON or lacks expected keys.")

    text = (response.text or "").strip()
    return (
        text
        if text.lower() not in {"", "null", "none", "undefined"}
        else "No meaningful response."
    )


async def _call_n8n_webhook(url: str, query: str, state: AppTurnState) -> str:
    """Call N8N webhook with proper error handling."""
    try:
        payload = _prepare_payload(query, state)
        async with httpx.AsyncClient(timeout=120.0) as client:
            if webhook_auth_username and webhook_auth_password:
                resp = await client.post(
                    url, json=payload, auth=(webhook_auth_username, webhook_auth_password)
                )
            else:
                resp = await client.post(url, json=payload)
        return _process_response(resp)

    except httpx.TimeoutException as exc:
        msg = "N8N service timeout."
        raise N8NConnectionError(msg) from exc
    except httpx.ConnectError as exc:
        msg = "Unable to connect to N8N service."
        raise N8NConnectionError(msg) from exc


async def handle_n8n_mcp_request(context: TurnContext, state: AppTurnState) -> str:
    """Handle N8N MCP request with comprehensive error handling."""
    try:
        if not context or not state:
            return "Internal error: invalid request context"

        url = _validate_n8n_configuration()
        query = _get_user_query(context)
        return await _call_n8n_webhook(url, query, state)

    except (N8NConfigurationError, N8NConnectionError) as e:
        return str(e)
