import logging

from botbuilder.core import TurnContext
from langchain_core.prompts import ChatPromptTemplate

from src.adaptive_cards.card_utils import create_error_card, send_adaptive_card
from src.adaptive_cards.modify_page_cards import (
    create_confirm_add_page_card,
    create_remove_source_selection_card,
    create_source_selection_card,
    select_source_page,
)
from src.bots.data_model.app_state import AppTurnState
from src.bots.storage.postgres_storage import PostgresStorage
from src.config.fastapi_config import fastapi_settings
from src.services.confluence_service.services.confluence_service import (
    ConfluenceService,
)
from src.services.custom_llm.services.llm_utils import LLMUtils
from src.services.manage_rag_sources.services.manage_source import (
    ManageSource,
)

_logger = logging.getLogger(__name__)

# Use the new configuration system to get the database URL
storage = PostgresStorage(connection_string=fastapi_settings.db.database_url)


async def handle_show_page_request(context: TurnContext, state: AppTurnState) -> str:
    """Handles requests to show a Confluence page from the RAG system."""
    # Start a multi-turn conversation to collect the information
    state.user.show_page_flow = {
        "active": True,
        "step": "start",
        "source_name": None,
        "page_id": None,
    }

    user_id = context.activity.from_property.id
    # Get available sources
    user_sources = await get_available_sources(user_id)  # Renamed for clarity
    common_sources_objects = ManageSource.get_common_source_names()  # Renamed for clarity

    common_sources_list = []
    if common_sources_objects:
        common_sources_list = [{"id": source.id, "name": str(source.name)} for source in common_sources_objects]

    # Check if both user_sources and common_sources_list are empty
    if not user_sources and not common_sources_list:
        # Send a card instead of text to prevent AI Planner from generating text response
        card = create_error_card(
            title="⚠️ No Knowledge Sources Available",
            message="No available knowledge sources found. Please create a knowledge base first.",
        )
        await send_adaptive_card(context, card)
        return "Showing page/document function called but no available knowledge sources found. Please create a personal knowledge base or choose available common data sources first."

    # Create source page card for removal
    source_card = select_source_page(user_sources, common_sources_list)

    await send_adaptive_card(context, source_card)
    return "Just return adaptive card displaying list of pages/documents to user, stop all actions and let user interact with the adaptive card."


async def handle_remove_page_request(context: TurnContext, state: AppTurnState) -> str:
    """Handles requests to remove a Confluence page from the RAG system."""
    # Start a multi-turn conversation to collect the information
    user_id = context.activity.from_property.id
    if "remove_page_flow" not in state.user:
        state.user.remove_page_flow = {
            "active": True,
            "step": "start",
            "source_name": None,
            "page_id": None,
        }
    # Get available sources
    sources = await get_available_sources(user_id)
    if not sources:
        return "No available your knowledge sources found. Please you create a knowledge base first."
    # Create source selection card for removal
    source_card = create_remove_source_selection_card(sources)
    await send_adaptive_card(context, source_card)

    return "Action completed, just show adaptive card top user, stop all actions and let user interact with the adaptive card."


async def handle_add_page_request(context: TurnContext, state: AppTurnState) -> str:
    """Handle requests to add a Confluence page to the RAG system."""
    # Start a multi-turn conversation to collect the information
    user_id = context.activity.from_property.id
    page_id = await get_page_id_from_context(context)
    if "add_page_flow" not in state.user:
        state.user.add_page_flow = {
            "active": True,
            "step": "start",
            "source_name": None,
            "page_id": None,
        }

    sources = await get_available_sources(user_id)
    if sources is None or len(sources) == 0:
        return "No available your knowledge sources found. Please you create a knowledge base first."
    source_card = None

    if page_id is None:
        # If no page ID is provided, create a source selection card
        source_card = create_source_selection_card(sources)
    else:
        try:
            confluence = ConfluenceService()
            page_info = confluence.get_page_by_id(page_id)
            if not page_info:
                return "Page ID not found. Please try again."
            pages_child = await confluence.get_all_child_pages(page_id)
            page_child_info = [{"id": p.get("id"), "title": p.get("title")} for p in pages_child]
            if page_info:
                source_card = create_confirm_add_page_card(
                    page_parent_id=page_info.page_id,
                    page_parent_name=page_info.page_name,
                    pages_child=page_child_info,
                    sources=sources,  # Assuming the first source is selected
                )
        except Exception:
            return "Error extracting page ID. Please try again."

    # Only send if source_card is created
    if source_card:
        await send_adaptive_card(context, source_card)
    return "Action completed it just show adaptive card."


async def get_available_sources(user_id: str | None = None) -> list:
    """Get all available RAG sources using direct service call instead of API.

    Returns:
        list: A list of dictionaries, each containing 'id' and 'name' of a source.

    """
    try:
        sources_list = []
        # Get user-specific sources if user_id is provided
        if user_id:
            user_sources = ManageSource.get_source_name_by_user_id(user_id=user_id)
            if user_sources and isinstance(user_sources, list):
                for source in user_sources:
                    sources_list.append({"id": source.id, "name": source.name})

        return sources_list
    except Exception as e:
        _logger.error("Error fetching sources: %s", e)
        return []


async def get_page_id_from_context(context: TurnContext) -> str | None:
    """Extracts the page ID from the context activity text using Azure OpenAI.

    Returns:
        str: The extracted page ID, or None if not found or invalid.

    """
    user_text = context.activity.text

    prompt_text = f"""
    You are an AI assistant. Your job is to extract the full "page ID" from the text below.
    A page ID is a long number (typically 7–10 digits) that appears:
    - After the words "page id", "page", or
    - Inside a URL such as: https://infodation.atlassian.net/wiki/spaces/.../pages/3475243531/...
    ✅ Respond with **only** the full number (e.g., 3475243531). No explanation. No extra characters.
    ❌ If there's no page ID, return exactly "None".
    Text: "{user_text}"
    """.strip()

    try:
        llm = LLMUtils.get_azure_openai_llm(temperature=0, max_tokens=20, timeout=None, max_retries=2)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful assistant that extracts page IDs."),
                ("user", "{input}"),
            ],
        )

        chain = prompt | llm

        # Collect all chunks
        result_chunks = []
        async for chunk in chain.astream({"input": prompt_text}):
            if chunk.content:
                result_chunks.append(chunk.content)

        result = "".join(result_chunks).strip()
        return result if result.isdigit() else None

    except Exception as e:
        _logger.error("Error extracting page ID: %s", e)
        return None
