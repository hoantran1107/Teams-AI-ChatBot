from langchain_openai import AzureOpenAIEmbeddings

from src.config.settings import azure_embedding_deployment_name, azure_openai_endpoint, embedding_deployment
from src.services.custom_llm.services.llm_utils import LLMUtils

AZURE_EMBEDDING = AzureOpenAIEmbeddings(
    azure_endpoint=azure_openai_endpoint,
    azure_deployment=embedding_deployment,
    model=azure_embedding_deployment_name,
)

AZURE_LLM03 = LLMUtils.get_azure_openai_llm(temperature=0.3)
AZURE_LLM00 = LLMUtils.get_azure_openai_llm(temperature=0)
