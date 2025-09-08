"""N8N service for handling webhook operations."""

import logging
from typing import Any

import httpx

from src.config.settings import (
    n8n_webhook_url,
    webhook_auth_password,
    webhook_auth_username,
)
from src.services.n8n_services.models.n8n_models import HealthResponse, MCPRequest, MCPResponse
from src.services.n8n_services.services.exceptions import (
    N8NConfigurationError,
    N8NConnectionError,
    N8NServiceError,
)

logger = logging.getLogger(__name__)


class N8NService:
    """Service class for N8N webhook operations."""

    def __init__(self) -> None:
        """Initialize N8N service with configuration."""
        self.webhook_url = n8n_webhook_url
        self.auth_username = webhook_auth_username
        self.auth_password = webhook_auth_password
        self.timeout = 30.0

    def _validate_configuration(self) -> None:
        """Validate N8N configuration.

        Raises:
            N8NConfigurationError: If webhook URL is not configured
        """
        if not self.webhook_url:
            msg = "N8N MCP webhook token not configured"
            raise N8NConfigurationError(msg)

    def _prepare_payload(self, request: MCPRequest) -> dict[str, Any]:
        """Prepare payload for N8N webhook.

        Args:
            request: MCP request data

        Returns:
            Dictionary containing the webhook payload
        """
        return {
            "action": request.action,
            "sessionId": request.session_id,
            "chatInput": request.chat_input,
        }

    async def trigger_mcp_workflow(self, request: MCPRequest) -> MCPResponse:
        """Trigger MCP workflow via N8N webhook.

        Args:
            request: MCP request data

        Returns:
            MCPResponse: Response from N8N workflow

        Raises:
            N8NConfigurationError: If webhook is not configured
            N8NConnectionError: If connection to N8N fails
            N8NServiceError: For other unexpected errors
        """
        self._validate_configuration()

        try:
            logger.info("Triggering N8N MCP with action: %s", request.action)

            payload = self._prepare_payload(request)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    auth=(self.auth_username, self.auth_password),
                )
                response.raise_for_status()

            logger.info("N8N MCP webhook called successfully")
            return MCPResponse(
                message="MCP triggered",
                response=response.text,
            )

        except httpx.RequestError as e:
            logger.error("Error calling N8N MCP webhook: %s", e)
            msg = "Failed to connect to N8N MCP service"
            raise N8NConnectionError(msg) from e
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            msg = "Internal server error"
            raise N8NServiceError(msg) from e

    async def get_health_status(self) -> HealthResponse:
        """Get health status of N8N service.

        Returns:
            HealthResponse: Health status information
        """
        return HealthResponse(
            status="healthy",
            webhook_configured=bool(self.webhook_url),
            webhook_url="configured" if self.webhook_url else None,
        )
