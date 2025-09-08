"""N8N controller for handling HTTP requests."""

import logging

from fastapi import APIRouter, HTTPException

from src.services.n8n_services.models.n8n_models import HealthResponse, MCPRequest, MCPResponse
from src.services.n8n_services.services.n8n_service import (
    N8NConfigurationError,
    N8NConnectionError,
    N8NService,
    N8NServiceError,
)

router = APIRouter(
    prefix="/n8n",
    tags=["N8N"],
)

logger = logging.getLogger(__name__)


class N8NController:
    """Controller class for N8N endpoints."""

    def __init__(self) -> None:
        """Initialize controller with N8N service."""
        self.n8n_service = N8NService()

    async def trigger_mcp(self, request: MCPRequest) -> MCPResponse:
        """Handle MCP trigger request.

        Args:
            request: MCP request data

        Returns:
            MCPResponse: Response from MCP workflow

        Raises:
            HTTPException: For various error conditions
        """
        try:
            return await self.n8n_service.trigger_mcp_workflow(request)
        except N8NConfigurationError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except N8NConnectionError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        except N8NServiceError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def health_check(self) -> HealthResponse:
        """Handle health check request.

        Returns:
            HealthResponse: Health status information
        """
        return await self.n8n_service.get_health_status()


# Initialize controller
n8n_controller = N8NController()


@router.post("/mcp", response_model=MCPResponse)
async def trigger_mcp(request: MCPRequest) -> MCPResponse:
    """Trigger MCP workflow via N8N webhook.

    Args:
        request: MCP request containing action, session_id, and chat_input

    Returns:
        MCPResponse: Result of the MCP workflow trigger
    """
    return await n8n_controller.trigger_mcp(request)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check for N8N service.

    Returns:
        HealthResponse: Current health status of the N8N service
    """
    return await n8n_controller.health_check()
