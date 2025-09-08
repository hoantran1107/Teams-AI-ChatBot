"""N8N service specific exceptions."""


class N8NIntegrationError(Exception):
    """Base exception for N8N integration errors."""


class N8NConfigurationError(N8NIntegrationError):
    """Raised when N8N configuration is invalid or missing."""


class N8NConnectionError(N8NIntegrationError):
    """Raised when unable to connect to N8N service."""

class N8NServiceError(Exception):
    """Base exception for N8N service errors."""
