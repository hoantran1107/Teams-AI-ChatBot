from langchain.retrievers.multi_query import LineListOutputParser
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)

from src.constants.llm_constant import AZURE_LLM00


async def create_queries(human_message: str, histories: list):
    """Generate alternative queries for document retrieval.

    This method generates three alternative versions of a given user question
    to improve retrieval from a vector database. It uses a language model chain
    to process the input and produce the output.

    Args:
            human_message (str): The original user question.
            histories (list): The chat history containing previous messages.

    Returns:
        list[str]: A list of three alternative queries.

    """
    output_parser = LineListOutputParser()
    prompt_ = ChatPromptTemplate(
        [
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template(
                template=(
                    "You are an AI language model assistant. Your task is "
                    "to generate 3 ENGLISH different versions of the given user "
                    "question to retrieve relevant documents from a vector database. "
                    "By generating multiple perspectives on the user question, "
                    "your goal is to help the user overcome some of the limitations "
                    "of distance-based similarity search. "
                    "\nWhen resolving references in the current question, PRIORITIZE the MOST RECENT "
                    "messages in the chat history. Focus on the immediate context from the latest "
                    "exchange first before considering older messages. "
                    "Make each alternative question standalone and complete with all necessary context. "
                    "Provide these alternative questions separated by newlines. "
                    "\nOriginal question: {question} "
                ),
            ),
        ],
    )
    llm_chain = prompt_ | AZURE_LLM00 | output_parser
    queries = await llm_chain.ainvoke(
        {"question": human_message, "chat_history": histories},
    )

    return queries
