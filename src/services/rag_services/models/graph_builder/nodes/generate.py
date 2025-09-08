from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.types import StreamWriter

from src.constants.llm_constant import AZURE_LLM03
from src.services.rag_services.models.graph_builder.prompts import (
    HUMAN_PROMPT,
    SYSTEM_PROMPT,
)
from src.services.rag_services.models.graph_builder.state import GraphState
from src.services.rag_services.url_shortening_service import url_shortening_service


def _add_to_history_simple(state: GraphState, response_content: str):
    """Simple version of adding messages to history.

    Args:
        state (GraphState): The current state of the graph.
        response_content (str): The content of the response to add to the history.

    """
    if not state.get("history"):
        state["history"] = []

    question = state.get("question", "")

    # Add user question
    if question and len(question.strip()) > 3:
        state["history"].append(HumanMessage(content=question))

    # Add AI response (exclude error messages)
    if response_content and len(response_content.strip()) > 10 and not response_content.startswith("Error"):
        state["history"].append(AIMessage(content=response_content))


def write_prompt(state: GraphState):
    """Generates a chat prompt based on the given graph state.

    Args:
        state (GraphState): The current state of the graph.

    """
    using_memory = state.get("using_memory", False)
    question = state["question"]
    language = state.get("language")
    documents = state.get("documents", [])
    analysis_results = state.get("analysis_results", None)
    classification_message = state["classification_message"]
    node_message = state.get("node_message", {})
    persona_instructions = state.get("instructions", [])
    formatted_contexts = _define_document_context(
        analysis_results,
        classification_message,
        documents,
    )

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    personal_instruction_dict = {
        item["name"]: item["instructions"].encode("utf-8").decode("utf-8") for item in persona_instructions
    }
    if not using_memory:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT.format(language=language)),
            HumanMessage(content=question),
        ]
    else:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT.format(language=language)),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessage(
                content=HUMAN_PROMPT.format(
                    question=question,
                    current_time=current_time,
                    user_context="",
                    interaction_instruction=personal_instruction_dict,
                ),
            ),
        ]

    if formatted_contexts:
        messages.append(SystemMessage(content=formatted_contexts))
    if classification_message in ("feedback", "mixed_feedback") and node_message and using_memory:
        instruction_node_message = node_message["save_instructions"]
        messages.append(AIMessage(content=instruction_node_message))

    prompt = ChatPromptTemplate(messages=messages)

    return prompt


def _define_document_context(
    analysis_results,
    classification_message,
    documents,
):
    """Constructs a formatted context string based on the provided analysis results, classification message, and documents.

    Args:
        analysis_results (str): Analysis results to include in the context, if available.
        classification_message (str): Classification message indicating the type of interaction
                                (e.g., 'greeting', 'feedback').
        documents (list[dict]): A list of document dictionaries, each containing metadata
                                and content.

    Returns:
        str: A formatted string representing the context, including document details
        and analysis results, if applicable.

    """
    # Early return for greeting or feedback messages
    if classification_message in ("greeting", "feedback"):
        return ""

    # Start building context
    formatted_contexts = (
        "Contexts:\n- Document List: These are some of the documents that may be relevant to my question:\n"
    )

    # Add document contexts if available
    formatted_contexts = _add_document_contexts(
        formatted_contexts,
        documents,
    )

    # Add analysis results if available
    if analysis_results:
        formatted_contexts += _format_analysis_results(analysis_results)

    return formatted_contexts


def _add_document_contexts(formatted_contexts, documents):
    """Helper function to format document contexts."""
    if not documents:
        formatted_contexts += "No relevant documents found.\n\n"
        return formatted_contexts

    pattern = "{index}. {topic}\n```\n{content}\n```\n\n"

    for idx, doc in enumerate(documents, 1):
        metadata = doc.get("metadata", {})
        view_url = metadata.get("view_url", None)
        topic = metadata["topic"]
        document_collection = metadata.get("document_collection", "Unknown Collection")

        # Format the topic with URL first
        if view_url:
            try:
                # Use URL shortening service for better citation display
                short_url, _ = url_shortening_service.shorten_url(view_url)
                topic_with_url = f"**🔗 [{topic}]({short_url}) **"
            except Exception:
                # Fallback to original URL if shortening fails
                topic_with_url = f"**🔗 [{topic}]({view_url}) **"
        else:
            topic_with_url = topic

        # Add document collection on a new line
        topic_name = f"{topic_with_url}\n**Document Collection: {document_collection} **"

        formatted_contexts += pattern.format(
            index=idx,
            topic=topic_name,
            content=doc["content"],
        )

    return formatted_contexts


def _format_analysis_results(analysis_results):
    """Format analysis results for context."""
    return (
        f"- These are some of the analysis results for some table data, which can be helpful to "
        f"answer my question (dont include these analysis results in Citation Part):\n```\n{analysis_results}\n```\n"
    )


async def generate(state: GraphState, writer: StreamWriter):
    """Generate answer."""
    new_prompt = write_prompt(state)
    chain = new_prompt | AZURE_LLM03
    all_stream = ""

    try:
        async for stream_content in chain.astream(
            {"chat_history": state.get("history", [])},
        ):
            if isinstance(stream_content.content, str):
                all_stream += stream_content.content
            else:
                error_message = f"Stream content is not a string: {stream_content.content}"
                raise TypeError(error_message)

            writer({"generate": stream_content.content})

        # Add current interaction to history with quality checks
        _add_to_history_simple(state, all_stream)

    except Exception as e:
        # Simple error handling without API-specific processing
        error_message = str(e)
        writer({"generate": f"\n> ❌ **Error:**: {error_message}\n\n"})
        writer({"error": error_message})
        return ""

    return all_stream
