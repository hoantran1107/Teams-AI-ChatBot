from langchain_core.prompts import PromptTemplate

from src.constants.llm_constant import AZURE_LLM00
from src.services.rag_services.models.graph_builder.models.classify_message import ClassifyMessage
from src.services.rag_services.models.graph_builder.prompts import CLASSIFY_PROMPT


async def classify_message_node(user_message: str) -> str:
    """Classifies a user message into a specific category.

    Args:
        user_message (str): The message provided by the user to be classified.

    Returns:
        str: The category of the message as determined by the LLM.

    """
    prompt = PromptTemplate(
        template=CLASSIFY_PROMPT,
        input_variables=["text"],
    )
    llm_chain = prompt | AZURE_LLM00.with_structured_output(ClassifyMessage)
    response = await llm_chain.ainvoke({"text": user_message})

    return response.category
