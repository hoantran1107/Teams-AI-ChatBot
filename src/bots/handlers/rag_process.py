import logging
import traceback
import uuid

from botbuilder.core import TurnContext
from teams.ai.citations.citations import Appearance, ClientCitation
from teams.streaming import StreamingResponse

from src.bots.data_model.app_state import AppTurnState
from src.services.manage_rag_sources.services.manage_source import ManageSource
from src.services.rag_services.services.multiple_rag_sources import MultiRagService

_logger = logging.getLogger(__name__)


async def handle_rag_query(context: TurnContext, state: AppTurnState) -> str:
    """Handle RAG query requests."""
    res = await process_rag_query(context.data.get("query", ""), context, state)
    return str(res)


def _get_user_and_session_info(context, state):
    """Extract user and session information from context and state."""
    user_id = context.activity.from_property.id if context.activity.from_property else None
    user_name = context.activity.from_property.name if context.activity.from_property else None
    session_id = state.conversation.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        state.conversation.session_id = session_id
    return user_id, user_name, session_id


def _prepare_data_sources_from_state(state, user_id):
    data_sources = []

    if not hasattr(state.user, "data_sources"):
        _get_common_source(data_sources)
        return data_sources

    sources_config = state.user.data_sources
    if not isinstance(sources_config, dict):
        _get_common_source(data_sources)
        return data_sources

    _add_user_sources(data_sources, sources_config, user_id)
    _add_common_sources(data_sources, sources_config)

    return data_sources


def _add_user_sources(data_sources, sources_config, user_id):
    """Add user-specific sources to data_sources list."""
    if not user_id:
        return

    user_sources = sources_config.get("user", [])
    user_sources_name = ManageSource.get_source_by_name_and_user_id(user_sources, user_id)

    for source in user_sources_name:
        data_sources.append({"source_name": source.name, "user_id": user_id})


def _add_common_sources(data_sources, sources_config):
    """Add common sources to data_sources list."""
    common_sources = sources_config.get("common", [])
    for source in common_sources:
        data_sources.append({"source_name": source, "user_id": None})


def _clear_streamer_citations(streamer):
    if streamer.citations is not None:
        while len(streamer.citations) > 0:
            streamer.citations.pop()


async def process_stream_chunks(
    multi_rag_service: MultiRagService,
    streamer,
    query,
    data_sources,
    session_id,
    user_id,
    user_name,
    analysis_mode,
    language,
):
    """Process and stream chunks from the RAG service."""
    queue_len = 0
    citation_json, _table_data = None, None
    saved_queue_information = []
    async for chunk in multi_rag_service.stream_response(
        query,
        data_sources=data_sources,
        session_id=session_id,
        user_id=user_id,
        user_name=user_name,
        analysis_mode=analysis_mode,
        language=language,
    ):
        try:
            result = process_chunk(
                chunk,
                streamer,
                queue_len,
                saved_queue_information,
            )
            if "citation_json" in result:
                citation_json = result["citation_json"]
            elif "table_data" in result:
                _table_data = result["table_data"]
            elif "queue_len" in result:
                queue_len = result["queue_len"]
        except ValueError:
            _logger.exception("Error processing chunk")
    return citation_json, _table_data, queue_len


async def process_rag_query(query, context: TurnContext, state: AppTurnState):
    """Process a RAG query and return the full response text instead of streaming it."""
    user_id, user_name, session_id = _get_user_and_session_info(context, state)
    streamer = StreamingResponse(context)
    streamer.set_feedback_loop(True)
    streamer.set_generated_by_ai_label(True)
    _clear_streamer_citations(streamer)
    data_sources = _prepare_data_sources_from_state(state, user_id)
    analysis_mode = getattr(state.user, "analysis_mode", False)
    is_using_generate_node = True
    multi_rag_service = MultiRagService(is_using_generate_node=is_using_generate_node)
    citation_json, _, _ = None, None, 0
    try:
        streamer.queue_informative_update("Processing RAG response...")

        citation_json, _, _ = await process_stream_chunks(
            multi_rag_service,
            streamer,
            query,
            data_sources,
            session_id,
            user_id,
            user_name,
            analysis_mode,
            language=context.data.get("language", "en"),
        )

        await streamer.wait_for_queue()
        add_citations_to_response(streamer, citation_json)
    except Exception as e:
        _logger.error(
            f"Error processing RAG query: {e}. Traceback: {traceback.format_exc()}",
            exc_info=True,
        )
    finally:
        await streamer.end_stream()
    if citation_json and not is_using_generate_node:
        return [{"documents": citation_json}]
    return streamer.message


def _get_common_source(data_sources):
    common_sources = ManageSource.get_common_source_names()
    for source in common_sources:
        data_sources.append({"source_name": source.name, "user_id": None})


def _prepare_data_sources(state, user_id):
    """Prepare data sources based on user state.

    Args:
        state (AppTurnState): The application state
        user_id (str): The user ID

    Returns:
        tuple: (data_sources, analysis_mode)

    """
    data_sources = []
    if not state:
        _get_common_source(data_sources)
        return data_sources, False

    analysis_mode = state.user.get("analysis_mode", False)
    sources_config = state.user.get("data_sources")

    if not isinstance(sources_config, dict):
        _get_common_source(data_sources)
        return data_sources, analysis_mode

    user_sources = sources_config.get("user", [])
    if user_sources:
        user_sources_name = ManageSource.get_source_by_name_and_user_id(user_sources, user_id)
        data_sources.extend({"source_name": source.name, "user_id": user_id} for source in user_sources_name)

    common_sources = sources_config.get("common", [])
    data_sources.extend({"source_name": source, "user_id": None} for source in common_sources)

    return data_sources, analysis_mode


def _handle_citation_chunk(chunk_content, streamer, saved_info):
    message = (
        (f"Found {len(chunk_content)} relevant documents that can be helpful. I will read through them now...")
        if chunk_content
        else "Found no relevant documents."
    )
    if message not in saved_info:
        saved_info.append(message)
        streamer.queue_informative_update("\n\n".join(saved_info))
    return {"citation_json": chunk_content}


def _handle_picked_sources_chunk(chunk_content, streamer, saved_info):
    if chunk_content and chunk_content not in saved_info:
        saved_info.append(chunk_content)
        streamer.queue_informative_update("\n\n".join(saved_info))
    return {"picked_sources": chunk_content}


def _handle_save_instructions_chunk(chunk_content, streamer, saved_info):
    if not saved_info:
        saved_info.append(chunk_content)
    elif "Updating memory" not in saved_info[0]:
        saved_info.insert(0, chunk_content)
    else:
        saved_info[0] = chunk_content
    streamer.queue_informative_update("\n\n".join(saved_info))
    return {"save_instructions": chunk_content}


def _handle_table_chunk(chunk_content, streamer, _saved_info):
    streamer.queue_informative_update("Analyze relevant tables...")
    return {"table_data": chunk_content}


def _handle_full_response_chunk(chunk_content, _streamer, _saved_info):
    return {"full_response": chunk_content}


CHUNK_HANDLERS = {
    "citation": _handle_citation_chunk,
    "picked_sources": _handle_picked_sources_chunk,
    "save_instructions": _handle_save_instructions_chunk,
    "table": _handle_table_chunk,
    "full_response": _handle_full_response_chunk,
}


def process_chunk(
    chunk,
    streamer: StreamingResponse,
    queue_len,
    saved_queue_information,
):
    """Process individual chunks from the RAG service stream."""
    if not chunk or not isinstance(chunk, dict):
        raise ValueError(f"Unknown chunk type: {chunk}")

    if "msg" in chunk:
        streamer.queue_text_chunk(chunk["msg"])
        return {"queue_len": queue_len}

    for key, handler in CHUNK_HANDLERS.items():
        if key in chunk:
            return handler(chunk[key], streamer, saved_queue_information)

    raise ValueError(f"Unknown chunk value: {chunk}")


def add_citations_to_response(streamer: StreamingResponse, citation_json):
    """Add formatted citations to the response."""
    if not citation_json:
        return

    streamer.queue_text_chunk("\n\n---\n\n## 🔎 Relevant Documents: ")
    MAX_ACCEPTABLE_CITATION = 20
    for i, citation in enumerate(citation_json[:MAX_ACCEPTABLE_CITATION], 1):
        # Add citation number to text
        citation_text = f" [{i}] "
        streamer.queue_text_chunk(citation_text)

        # Add to Teams citation system
        url = citation.get("view_url")
        streamer.citations.append(
            ClientCitation(
                position=i,
                appearance=Appearance(
                    name=f"[{citation.get('topic', 'Unknown Source')}] Collection: {citation.get('document_collection', 'Unknown Collection')}",
                    abstract=f"{citation.get('titles', 'Untitled')[:155]}...",
                    url=url if url and url != "none" else None,
                ),
            ),
        )


async def get_rag_query_response(query: str, context: TurnContext = None, state: AppTurnState = None):
    """Process a RAG query and return the full response text instead of streaming it.

    Args:
        query (str): The query text
        context (TurnContext, optional): The Teams turn context. Defaults to None.
        state (AppTurnState, optional): The application state. Defaults to None.

    Returns:
        dict: A dictionary containing:
            - 'response': The full text response
            - 'citations': List of citation information if any
            - 'table_data': Table data if analysis mode was active

    """
    # Initialize return values
    result = {"response": "", "citations": None, "table_data": None}
    try:
        # Get user information from context if available
        user_id = None
        if context and context.activity.from_property:
            user_id = context.activity.from_property.id

        # Prepare data sources and analysis mode setting
        data_sources, analysis_mode = _prepare_data_sources(state, user_id)

        # Collect full response using MultiRagService.ask_with_no_memory_multi
        response = await MultiRagService.ask_with_no_memory_multi(
            question=query,
            rag_sources=data_sources,
            analyze_mode=analysis_mode,
        )
        # Set the response
        result["response"] = response  # Additional processing for citations can be added here if needed

    except Exception as e:
        _logger.error(
            f"Error in get_rag_query_response: {e}. Traceback: {traceback.format_exc()}",
            exc_info=True,
        )
        result["response"] = f"I encountered an error while processing your query: {e!s}"

    return result
