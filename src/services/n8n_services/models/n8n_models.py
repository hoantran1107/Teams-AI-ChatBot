"""N8N models for request/response data structures."""

from pydantic import BaseModel


class MCPRequest(BaseModel):
    """Request model for triggering MCP workflow via N8N webhook.

    Attributes:
        action: The action to perform (default: "sendMessage")
        session_id: The session identifier (default: "session_id")
        chat_input: The chat input message (default: "string")
    """

    action: str = "sendMessage"
    session_id: str = "session_id"
    chat_input: str = "string"


class MCPResponse(BaseModel):
    """Response model for MCP workflow.

    Attributes:
        message: Status message
        response: Response from N8N webhook
    """

    message: str
    response: str


class HealthResponse(BaseModel):
    """Health check response model.

    Attributes:
        status: Service status
        webhook_configured: Whether webhook is configured
        webhook_url: Webhook URL status
    """

    status: str
    webhook_configured: bool
    webhook_url: str | None
