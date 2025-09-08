"""AI configuration module.

Contains all AI-related configuration settings including Azure OpenAI.
"""

from src.config.environment import env


class AzureOpenAIConfig:
    """Azure OpenAI API configuration."""

    # API credentials and endpoints
    api_key = env.get_required("AZURE_OPENAI_API_KEY")
    azure_openai_endpoint = (
        env.get_required("AZURE_OPENAI_ENDPOINT") or "https://ifd-copilot-openai-dev.openai.azure.com"
    )

    # Model deployments
    azure_openai_model_deployment_name = env.get_str(
        "AZURE_OPENAI_MODEL_DEPLOYMENT_NAME",
        "model-router",
    )

    # API versions
    chat_api_version = env.get_str("AZURE_CHAT_API_VERSION", "2025-01-01-preview")
    embedding_api_version = env.get_str("AZURE_EMBEDDING_API_VERSION", "2023-05-15")

    # Embedding models
    azure_embedding_model = env.get_str(
        "AZURE_EMBEDDING_MODEL",
        "text-embedding-ada-002",
    )
    embedding_deployment = env.get_str(
        "EMBEDDING_DEPLOYMENT",
        "ifd-text-embedding-3-small",
    )


class AIConfig:
    """Combined AI configuration."""

    azure = AzureOpenAIConfig()


# Create singleton instance
ai_config = AIConfig()
