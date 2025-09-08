from langchain_openai import AzureChatOpenAI
from pydantic import SecretStr

from src.config.settings import (
    api_key,
    azure_chat_api_version,
    azure_chat_deployment_name,
    azure_openai_endpoint,
)


class LLMUtils:
    """Utility class for managing LLM configurations and instances."""

    @staticmethod
    def get_azure_openai_llm(
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | tuple[float, float] | None = None,
        max_retries: int | None = 2,
    ) -> AzureChatOpenAI:
        """Get an instance of AzureChatOpenAI with specified parameters."""
        return AzureChatOpenAI(
            azure_deployment=azure_chat_deployment_name,
            api_version=azure_chat_api_version,
            api_key=SecretStr(api_key),
            azure_endpoint=azure_openai_endpoint,
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            streaming=True,
        )
