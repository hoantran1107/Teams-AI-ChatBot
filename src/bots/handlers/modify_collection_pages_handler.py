import logging
import os
from datetime import datetime
from uuid import uuid4

from botbuilder.core import MessageFactory, TurnContext
from botbuilder.schema import Activity, ActivityTypes, Attachment

from src.adaptive_cards.card_utils import (
    create_basic_card,
    create_error_card,
    create_filter_info,
    create_success_card,
    send_adaptive_card,
)
from src.adaptive_cards.modify_page_cards import (
    create_confirmation_dialog,
    create_pages_by_source_card,
    create_search_container,
)
from src.bots.data_model.app_state import AppTurnState
from src.constants.app_constants import AdaptiveCardConst
from src.services.confluence_service.services.confluence_service import ConfluenceService
from src.services.cronjob.services.document_rag import CronjobDocumentRag
from src.services.manage_rag_sources.services.manage_source import ManageSource
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import Collection, SourceType
from src.services.rag_services.url_shortening_service import url_shortening_service
from urllib.parse import urlparse

DEFAULT_LOCAL_API_URL = "localhost:5000"
UNTITLE_PAGE = "Untitled Page"
UNKNOWN_DATE = "Unknown date"
_logger = logging.getLogger(__name__)
api_base_url = os.environ.get("LOCAL_API_URL", DEFAULT_LOCAL_API_URL)


async def __send_typing_indicator(context: TurnContext) -> None:
    """Send a typing indicator activity to the user."""
    typing_activity = Activity(type=ActivityTypes.typing)
    await context.send_activity(typing_activity)


async def handle_show_page_actions(context: TurnContext, state: AppTurnState) -> None:
    """Handles actions related to showing pages."""
    # Fix: Check if context.activity.value is not None
    action = context.activity.value.get("action", "") if context.activity.value else ""

    if action in ["show_page_source_selected", "apply_search", "clear_search"]:
        # Process source selection
        await process_show_page(context, state)

    if action in ["show_page_prev_page", "show_page_next_page"]:
        direction = 1 if action == "show_page_next_page" else -1
        await __navigate_pages(context, state, direction)


# Move __navigate_pages to top-level scope
async def __navigate_pages(context: TurnContext, state: AppTurnState, direction: int) -> None:
    """Handles pagination for showing pages."""
    user_state = getattr(state, "user", state)
    # Retrieve pagination state
    show_page_flow = getattr(user_state, "show_page_flow", {})
    pages = show_page_flow.get("all_pages", [])
    page_size = show_page_flow.get("page_size", 20)
    total_pages = show_page_flow.get("total_pages", 1)
    current_page = show_page_flow.get("current_page", 1)
    collection_user_id = show_page_flow.get("collection_user_id", None)

    # Update current page based on direction
    new_page = current_page + direction
    if new_page < 1:
        new_page = 1
    elif new_page > total_pages:
        new_page = total_pages

    show_page_flow["current_page"] = new_page

    start_idx = (new_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(pages))
    current_pages = pages[start_idx:end_idx]

    # Create simple page list
    page_items = []
    __process_paging(page_items, current_pages, start_idx, collection_user_id)

    # Prepare card components
    collection_name = show_page_flow.get("source_name", "Knowledge Base")
    collection_id = show_page_flow.get("collection_id", "")
    search_text = show_page_flow.get("search_text", "")
    all_pages = show_page_flow.get("all_unfiltered_pages", pages)

    card_body = [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": f"📚 Pages in {collection_name}",
            "weight": "Bolder",
            "size": "Medium",
        },
    ]

    # Add search container
    search_container = create_search_container(
        "Search by page name or ID...",
        search_text,
        "apply_search",
        collection_id,
    )
    card_body.append(search_container)

    # Add filter info if filtering is active
    if search_text:
        extension = {"sourceSelection": collection_name}
        filter_info = create_filter_info(len(pages), len(all_pages), search_text, "clear_search", **extension)
        card_body.append(filter_info)

    # Add pagination info
    card_body.extend(
        [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": f"Showing {start_idx + 1}-{end_idx} of {len(pages)} pages",
                "wrap": True,
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": f"Page {new_page} of {total_pages}",
                "horizontalAlignment": "Center",
                "weight": "Bolder",
                "color": AdaptiveCardConst.COLOR_ACCENT,
                "spacing": "Small",
            },
        ],
    )

    # Add page items
    card_body.extend(page_items)

    # Create pagination buttons
    actions = []
    if total_pages > 1:
        if new_page > 1:
            actions.append(
                {
                    "type": AdaptiveCardConst.ACTION_SUBMIT,
                    "title": "Previous",
                    "data": {"action": "show_page_prev_page"},
                },
            )
        if new_page < total_pages:
            actions.append(
                {
                    "type": AdaptiveCardConst.ACTION_SUBMIT,
                    "title": "Next",
                    "data": {"action": "show_page_next_page"},
                },
            )

    # Create the card content
    card_content = {
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_3,
        "body": card_body,
        "actions": actions,
    }

    # Update existing activity
    if show_page_flow.get("message_id"):
        update_activity = MessageFactory.attachment(
            Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card_content),
        )
        update_activity.id = show_page_flow["message_id"]
        await context.update_activity(update_activity)
    else:
        response = await context.send_activity(
            MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card_content)),
        )
        if response is not None and hasattr(response, "id"):
            show_page_flow["message_id"] = response.id


async def handle_remove_page_actions(context: TurnContext, state: AppTurnState) -> None:
    """Handle all actions related to page removal."""
    # Fix: Check if context.activity.value is not None
    action = context.activity.value.get("action", "") if context.activity.value else ""

    action_handlers = {
        # Basic actions
        "remove_page_source_selected": process_remove_source_selection,
        # Source removal actions
        "remove_entire_source": process_remove_entire_source_request,
        "remove_entire_source_confirm": process_remove_entire_source,
        # Single page removal actions
        "remove_page_delete_request": process_page_deletion_request,
        "remove_page_confirm_delete": process_page_removal,
        # Multiple selection actions
        "remove_selected_sources": process_remove_multiple_sources_request,
        "remove_multiple_sources_confirm": process_remove_multiple_sources_removal,
        # Multiple pages removal actions
        "remove_selected_pages": process_selected_pages_deletion_request,
        "remove_selected_pages_confirm": process_selected_pages_removal,
    }

    # Handle direct action mappings
    if action in action_handlers:
        return await action_handlers[action](context, state)
    if action.startswith("page_") and "_toggled" in action:
        return await handle_page_toggle(context, state)

    # Handle navigation actions
    if action in ["remove_page_prev_page", "remove_page_next_page"]:
        direction = 1 if action == "remove_page_next_page" else -1
        return await navigate_remove_pages(context, state, direction)

    # Handle search/filter actions
    if action in ["remove_apply_search", "remove_clear_search"]:
        # Implement or call the correct filter logic here
        # For now, just send a message indicating this is not implemented
        await context.send_activity("Remove page filter functionality is not implemented yet.")
    return None


async def handle_page_toggle(context: TurnContext, state: AppTurnState) -> None:
    """Handles page toggles and updates selected_pages in state."""
    user_state = getattr(state, "user", state)
    form_data = context.activity.value or {}
    selected_pages = user_state.remove_page_flow.get("selected_pages", []) or []
    source_pages_map = user_state.remove_page_flow.get("source_pages_map", {})

    # Normalize persisted selections to a map by id
    persisted_map = {}
    for p in selected_pages:
        if isinstance(p, dict):
            pid = str(p.get("id") or p.get("page_id") or p.get("id"))
            persisted_map[pid] = dict(p)
        else:
            persisted_map[str(p)] = {"id": str(p), "page_id": str(p), "name": "", "source_id": ""}

    # Build a lookup map once: page_id (string) -> (page_obj, source_id)
    page_lookup = {}
    for source_id, pages in source_pages_map.items():
        for page in pages:
            for id_key in ("id", "page_id", "identity_constant_name", "pageId"):
                raw = page.get(id_key)
                if raw is None:
                    continue
                pid_str = str(raw)
                if pid_str and pid_str not in page_lookup:
                    page_lookup[pid_str] = (page, source_id)

    # Process incoming keys (page_* checkboxes) using the lookup map
    for key, value in form_data.items():
        if key.startswith("page_"):
            pid = key.replace("page_", "")
            if str(value).lower() == "true":
                # If the checkbox is checked, try to populate metadata from the lookup
                page_entry = page_lookup.get(str(pid))
                if page_entry is not None:
                    page_obj, src_id = page_entry
                    persisted_map[pid] = {
                        "id": str(pid),
                        "page_id": page_obj.get("identity_constant_name") or page_obj.get("page_id") or str(pid),
                        "name": page_obj.get("name", ""),
                        "source_id": src_id,
                        "source_type": page_obj.get("source_type"),
                    }
                else:
                    # fallback when metadata not found — keep behavior similar to previous implementation
                    persisted_map[pid] = {"id": pid, "page_id": pid, "name": "", "source_id": ""}
            else:
                # checkbox not checked: remove persisted entry if any
                persisted_map.pop(pid, None)

    # Persist merged selections
    user_state.remove_page_flow["selected_pages"] = list(persisted_map.values())

    # Recreate and update the card
    source_names_map = user_state.remove_page_flow.get("source_names_map", {})
    # Safely compute total_count: only count values that support len() to avoid exceptions on malformed data
    _spm = user_state.remove_page_flow.get("source_pages_map", {}) or {}
    total_count = sum(len(pages) for pages in _spm.values() if hasattr(pages, "__len__"))
    card = create_pages_by_source_card(source_pages_map, user_state.remove_page_flow.get("selected_pages", []), source_names_map, total_count=total_count)

    update_activity = MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card))

    message_id = user_state.remove_page_flow.get("message_id")
    if message_id:
        update_activity.id = message_id
        await context.update_activity(update_activity)
    else:
        response = await context.send_activity(update_activity)
        if response is not None and hasattr(response, "id"):
            user_state.remove_page_flow["message_id"] = response.id


async def process_remove_source_selection(context: TurnContext, state: AppTurnState) -> None:
    """Process the removal of source selection."""
    user_state = getattr(state, "user", state)
    if not hasattr(context.activity, "value") or not isinstance(context.activity.value, dict):
        return

    form_data = context.activity.value
    selected_sources = []

    # Process all keys in form_data
    for key, value in form_data.items():
        if key.startswith("source_") and value == "true":
            source_id = key.replace("source_", "")
            selected_sources.append(source_id)

    if not selected_sources:
        card = create_error_card(
            title="⚠️ No Knowledge Base Selected",
            message="Please select at least one knowledge base to manage.",
        )
        await send_adaptive_card(context, card)
        return

    # Initialize the removal flow state
    if "remove_page_flow" not in user_state:
        user_state.remove_page_flow = {}

    # Store the selected sources in state
    user_state.remove_page_flow["selected_sources"] = selected_sources
    user_state.remove_page_flow["step"] = "view_pages"

    await __send_typing_indicator(context)

    try:
        # Fetch pages for each selected source
        source_pages_map = {}
        source_names_map = {}

        for source_id in selected_sources:
            pages, collection_name, _ = await __fetch_pages_for_source(source_id)
            if pages and isinstance(pages, list):
                pages.sort(key=lambda x: x.get("updated_date_str", ""), reverse=True)
                source_pages_map[source_id] = pages  # Use source_id as key
                source_names_map[source_id] = collection_name  # Use source_id as key

        if source_pages_map:
            # Calculate total pages across all selected sources
            total_pages_count = sum(len(pages) for pages in source_pages_map.values())

            # If too many pages, enable pagination to avoid sending oversized messages.
            PAGE_SIZE = 6  # show 5-7 files per page as requested (choose 6)
            if total_pages_count > PAGE_SIZE:
                # Flatten pages into a single ordered list (keep most recent first)
                flattened = []
                for src_id, pages in source_pages_map.items():
                    for p in pages:
                        # annotate with source id/name for reference if needed
                        p_copy = dict(p)
                        p_copy["_source_id"] = src_id
                        p_copy["_source_name"] = source_names_map.get(src_id, str(src_id))
                        flattened.append(p_copy)

                # Sort flattened list by updated_date_str if available, desc
                # Sort flattened list by updated_date_str if available, desc.
                # Use a safe key that treats non-dict items as having an empty date
                # to avoid AttributeError and avoid silently swallowing exceptions.
                flattened.sort(
                    key=lambda x: x.get("updated_date_str", "") if isinstance(x, dict) else "",
                    reverse=True,
                )

                # Initialize pagination state in user_state
                user_state.remove_page_flow.update(
                    {
                        "all_pages": flattened,
                        "all_unfiltered_pages": list(flattened),
                        "page_size": PAGE_SIZE,
                        "total_pages": (len(flattened) + PAGE_SIZE - 1) // PAGE_SIZE,
                        "current_page": 1,
                        # store pages under a single key so paged view shows combined results
                        "source_pages_map": {"Selected": flattened},
                        "source_names_map": {"Selected": "Selected Knowledge Bases"},
                        "selected_pages": [],
                    }
                )

                # Render first page using existing paginator
                # Force new message to avoid updating an old buried card
                user_state.remove_page_flow["force_new_message"] = True
                await navigate_remove_pages(context, state, 0)
                return

            # If not too many pages, render full card as before
            for k, v in list(source_names_map.items()):
                source_names_map[str(k)] = str(v) if v is not None else str(k)

            total_count = sum(len(pages) for pages in source_pages_map.values())
            all_pages_flattened = []
            for src_id, pages in source_pages_map.items():
                for p in pages:
                    p_copy = dict(p)
                    p_copy.setdefault("_source_id", str(src_id))
                    # prefer explicit source name if available
                    p_copy.setdefault("_source_name", source_names_map.get(str(src_id), str(src_id)))
                    all_pages_flattened.append(p_copy)

            card = create_pages_by_source_card(source_pages_map, source_names_map=source_names_map, total_count=total_count)
            user_state.remove_page_flow["selected_pages"] = []
            response = await context.send_activity(
                MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card)),
            )

            # Store state for later use, include flattened all_pages for enrichment
            user_state.remove_page_flow.update(
                {
                    "source_pages_map": source_pages_map,
                    "source_names_map": source_names_map,
                    "message_id": response.id,
                    "selected_pages": [],
                    "all_pages": all_pages_flattened,
                    "all_unfiltered_pages": all_pages_flattened,
                },
            )
            return

        card = create_error_card(
            title="⚠️ No Pages Found",
            message="No pages were found in the selected knowledge bases.",
        )
        await send_adaptive_card(context, card)

    except Exception as e:
        card = create_error_card(
            title="❌ Error Retrieving Pages",
            message=f"Error: {e!s}",
        )
        await send_adaptive_card(context, card)


async def handle_add_page_actions(context: TurnContext, state: AppTurnState) -> None:
    """Handle actions related to adding a page to a collection."""
    if not hasattr(context.activity, "value") or not isinstance(context.activity.value, dict):
        return
    submitted_data = context.activity.value
    user_state = getattr(state, "user", state)
    source_name = submitted_data.get("sourceSelection")
    page_parent_id = submitted_data.get("pageId")
    enable_child_pages = submitted_data.get("enableChildPages", False)
    enable_all_child_pages = submitted_data.get("enableAllChildPages", False)
    if isinstance(enable_child_pages, str):
        enable_child_pages = enable_child_pages.lower() == "true"

    if isinstance(enable_all_child_pages, str):
        enable_all_child_pages = enable_all_child_pages.lower() == "true"
    pages_child_ids = []
    if enable_all_child_pages:
        # Fetch all child pages if not provided
        confluence = ConfluenceService()
        all_child_pages = await confluence.get_all_child_pages(page_parent_id)
        pages_child_ids = [item["id"] for item in all_child_pages]
    if enable_child_pages:
        for key, value in submitted_data.items():
            if key.startswith("childPage_") and value == "true":
                page_child_id = key.split("childPage_")[1]  # Extract page ID from the key : childPage_12345
                pages_child_ids.append(page_child_id)
    if source_name and page_parent_id:
        user_state.add_page_flow["source_name"] = source_name
        user_state.add_page_flow["page_id"] = page_parent_id

        await process_page_submission(
            context=context,
            user_state=user_state,
            collection_id=source_name,
            page_id=page_parent_id,
            enable_child_pages=enable_child_pages,
            pages_child_id=pages_child_ids,
        )


async def process_page_deletion_request(context: TurnContext, state: AppTurnState) -> None:
    """Show confirmation dialog for page deletion."""

    user_state = getattr(state, "user", state)
    if not hasattr(context.activity, "value") or not isinstance(context.activity.value, dict):
        return

    page_id = context.activity.value.get("pageId")
    page_name = context.activity.value.get("pageName", page_id)
    source_type = context.activity.value.get("sourceType")
    collection_id = context.activity.value.get("sourceId")
    if not page_id:
        return

    data_action = {
        "page_id": page_id,
        "page_name": page_name,
        "source_type": source_type,
        "source_id": collection_id,
    }
    # Ensure remove_page_flow exists and persist the values so the
    # confirmation handler and the actual removal step can access them.
    if "remove_page_flow" not in user_state:
        user_state.remove_page_flow = {}

    # Persist delete context unconditionally (avoid overwriting elsewhere
    # but ensure the keys are set so process_page_removal can read them).
    user_state.remove_page_flow.update(
        {
            "delete_page_id": page_id,
            "delete_page_name": page_name,
            "source_id": collection_id,
            "source_type": source_type,
        }
    )

    _logger.debug("Persisted remove_page_flow for deletion: %s", user_state.remove_page_flow)
    # Create confirmation dialog using our template
    confirmation_card = create_confirmation_dialog(
        title="⚠️ Confirm Page Deletion",
        message=f"Are you sure you want to remove page '{page_name}'?",
        confirm_action="remove_page_confirm_delete",
        data_action=data_action,
        is_destructive=True,
    )

    if user_state.remove_page_flow.get("message_confirmation_id", None):
        # Update existing confirmation message
        update_activity = MessageFactory.attachment(
            Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=confirmation_card),
        )
        update_activity.id = user_state.remove_page_flow["message_confirmation_id"]
        await context.update_activity(update_activity)
        return
    # Show the confirmation dialog and persist the message id for later updates
    response = await context.send_activity(
        MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=confirmation_card)),
    )
    if response is not None and hasattr(response, "id"):
        user_state.remove_page_flow["message_confirmation_id"] = response.id


async def process_page_removal(context: TurnContext, state: AppTurnState) -> None:
    """Process actual page deletion after confirmation."""
    user_state = getattr(state, "user", state)
    page_id = user_state.remove_page_flow.get("delete_page_id")
    page_name = user_state.remove_page_flow.get("delete_page_name", page_id)
    source_id = user_state.remove_page_flow.get("source_id")  # Using source_id as the collection_id
    source_type = user_state.remove_page_flow.get("source_type")
    if not (page_id and source_id):
        return

    await __send_typing_indicator(context)

    try:
        # Call the delete_confluence_pages_for_source method directly
        not_found_page_ids = await ManageSource.delete_pages_for_source(
            collection_id=source_id,
            page_ids=[page_id],
            source_type=SourceType.CONFLUENCE if source_type == "CONFLUENCE" else SourceType.GCP,
        )

        if page_id in not_found_page_ids:
            # The page wasn't found in the collection
            card = create_error_card(
                title="❌ Page Not Found",
                message=f"Page ID '{page_id}' not found in the knowledge base.",
            )
            await send_adaptive_card(context, card)
        else:
            # Send success message
            card = create_success_card(
                title="✅ Page Removed Successfully!",
                message=f"Page '{page_name}' has been removed from the knowledge base.",
            )
            await send_adaptive_card(context, card)

        # Update the pages view to reflect the deletion
        # Reload pages for the source
        pages, _, _ = await __fetch_pages_for_source(source_id)
        if pages and isinstance(pages, list):
            # Update the state with new page list
            pages.sort(key=lambda p: p.get("updated_date_str", ""), reverse=True)
            user_state.show_page_flow["all_unfiltered_pages"] = pages
            user_state.show_page_flow["all_pages"] = pages

            # Recalculate pagination
            page_size = user_state.show_page_flow.get("page_size", 10)
            total_pages = (len(pages) + page_size - 1) // page_size
            current_page = min(user_state.show_page_flow.get("current_page", 1), total_pages or 1)

            user_state.show_page_flow["current_page"] = current_page
            user_state.show_page_flow["total_pages"] = total_pages
            user_state.show_page_flow["search_text"] = ""

        # Update the page view
        await __navigate_pages(context, state, 0)  # refresh without changing page

    except Exception as e:
        # Send error message
        card = create_error_card(
            title="❌ Failed to Remove Page",
            message=f"Error: {e!s}",
        )
        await send_adaptive_card(context, card)
        _logger.error("Error removing page: %s", e, exc_info=True)


async def process_page_submission(
    context: TurnContext,
    user_state,
    collection_id: str | None = None,
    page_id: str | None = None,
    enable_child_pages: bool = False,
    pages_child_id: list[str] | None = None,
) -> None:
    """Processes a page submission to add a Confluence page to a knowledge base.

    Args:
        context: Turn context
        user_state: User state containing add_page_flow information
        source_name: Source/collection ID to add the page to
        page_id: The Confluence page ID to add
        enable_child_pages: Whether to include child pages (optional)
        pages_child_id: List of child page IDs to add (optional)

    """
    # Use provided parameters or get from context if not provided
    if not page_id:
        page_id = context.activity.value.get("pageId") if context.activity.value else None
    if not collection_id:
        collection_id = user_state.add_page_flow.get("source_name")

    # Ensure pages_child_id is always a list
    if pages_child_id is None:
        pages_child_id = []

    if page_id and collection_id:
        await __send_typing_indicator(context)
        try:
            # Call the add_page method directly with the page ID and collection ID
            collection_model_list = Collection.find_by_filter(id=collection_id)
            if not collection_model_list:
                raise ValueError(f"Collection with ID {collection_id} not found")

            collection_model = collection_model_list[0]
            new_page_info = await ConfluenceService().add_confluence_page(
                page_id=page_id,
                collection_id=int(collection_id),
                enable_child_pages=enable_child_pages,
                pages_child_id=pages_child_id,
            )
            # Check if operation was successful
            message = f"Page '{page_id}' has been added to '{collection_model.name}'."
            if pages_child_id:
                message += f" Child pages: {', '.join(pages_child_id)}"
            #  after adding the page, call the cronjob to update the collection
            cronjob_service = CronjobDocumentRag(collection_model)
            await cronjob_service.process_cronjob_async()
            if new_page_info:
                # Send success message
                card = create_success_card(
                    title="✅ Page Added Successfully!",
                    message=message,
                )
                await send_adaptive_card(context, card)
            else:
                raise ValueError("Failed to add page: No data returned from service")

        except ValueError as e:
            # Handle specific case for page not found
            error_msg = str(e)
            if "No content found with id" in error_msg:
                # Create a more helpful adaptive card with troubleshooting steps
                card = create_error_card(
                    title="❌ Page Not Found",
                    message=f"The page with ID `{page_id}` could not be found in Confluence.",
                    additional_items=[
                        {
                            "type": AdaptiveCardConst.CONTAINER,
                            "style": "emphasis",
                            "items": [
                                {
                                    "type": AdaptiveCardConst.TEXT_BLOCK,
                                    "text": "💡 Troubleshooting Steps:",
                                    "weight": "Bolder",
                                },
                                {
                                    "type": AdaptiveCardConst.FACT_SET,
                                    "facts": [
                                        {
                                            "title": "1.",
                                            "value": "Verify the page ID is correct",
                                        },
                                        {
                                            "title": "2.",
                                            "value": "Make sure the page exists in Confluence",
                                        },
                                    ],
                                },
                            ],
                        },
                        {
                            "type": AdaptiveCardConst.TEXT_BLOCK,
                            "text": "How to find the correct page ID:",
                            "weight": "Bolder",
                            "spacing": "Medium",
                        },
                        {
                            "type": AdaptiveCardConst.TEXT_BLOCK,
                            "text": "1. Open the Confluence page in your browser\n2. Look in the URL for 'pages/' followed by numbers\n",
                            "wrap": True,
                        },
                        {
                            "type": AdaptiveCardConst.TEXT_BLOCK,
                            "text": "Example: https://infodation.atlassian.net/wiki/spaces/IFDRD/pages/3331785283/Whitepaper",
                            "isSubtle": True,
                            "wrap": True,
                            "size": "Small",
                        },
                    ],
                )
                await send_adaptive_card(context, card)
                return
            # Send generic error message
            card = create_error_card(
                title="❌ Failed to Add Page",
                message=f"Error: {error_msg}",
            )
            await send_adaptive_card(context, card)
        except Exception as e:
            # Send generic error message for any other exceptions
            card = create_error_card(
                title="❌ Failed to Add Page",
                message=f"Error: {e!s}",
            )
            await send_adaptive_card(context, card)

        # Reset page ID in user state
        if "add_page_flow" in user_state:
            user_state.add_page_flow["page_id"] = None


async def process_show_page(context: TurnContext, state: AppTurnState) -> None:
    """Process source selection for showing pages and display list of available pages."""
    user_state = getattr(state, "user", state)

    if not hasattr(context.activity, "value") or not isinstance(context.activity.value, dict):
        return

    selected_source = context.activity.value.get("sourceSelection")
    search_text = context.activity.value.get("searchQuery", "")
    apply_filter = context.activity.value.get("action") == "apply_search"
    clear_filter = context.activity.value.get("action") == "clear_search"

    # Determine if this is an update to an existing card (search/filter)
    is_update = (apply_filter or clear_filter) and "message_id" in user_state.show_page_flow

    # Handle source selection
    if selected_source:
        user_state.show_page_flow["collection_id"] = selected_source
        user_state.show_page_flow["step"] = "view_pages"
        user_state.show_page_flow["search_text"] = ""  # Reset search on new source

        await __send_typing_indicator(context)
        try:
            # Fetch available pages for this source
            pages, collection_name, collection_user_id = await __fetch_pages_for_source(selected_source)
            user_state.show_page_flow["source_name"] = collection_name
            user_state.show_page_flow["collection_user_id"] = collection_user_id
            if not pages or not isinstance(pages, list):
                card = create_error_card(
                    title="📚 No Pages Found",
                    message="No pages were found in the knowledge base.",
                )
                await send_adaptive_card(context, card)
                return

            # Sort pages by updated date for better browsing
            pages.sort(key=lambda x: x.get("updated_date_str", ""), reverse=True)

            # Store all pages for filtering later
            all_pages = pages
            user_state.show_page_flow["all_unfiltered_pages"] = all_pages

            # Handle search/filter actions
            if apply_filter and search_text:
                # Store search text in state
                user_state.show_page_flow["search_text"] = search_text
                # Filter pages by search text
                search_lower = search_text.lower()
                pages = [
                    page
                    for page in pages
                    if (
                        search_lower in page.get("page_name", "").lower()
                        or search_lower in page.get("page_id", "").lower()
                    )
                ]
            elif clear_filter:
                # Clear search filter
                user_state.show_page_flow["search_text"] = ""
                search_text = ""
                pages = all_pages
            else:
                # Use existing search text from state
                search_text = user_state.show_page_flow.get("search_text", "")
                if search_text:
                    # Apply existing filter
                    search_lower = search_text.lower()
                    pages = [
                        page
                        for page in pages
                        if (
                            search_lower in page.get("page_name", "").lower()
                            or search_lower in page.get("page_id", "").lower()
                        )
                    ]

            # Pagination
            page_size = 20
            total_pages = (len(pages) + page_size - 1) // page_size
            current_page = 1

            # Store pagination data for later navigation
            user_state.show_page_flow["all_pages"] = pages
            user_state.show_page_flow["current_page"] = current_page
            user_state.show_page_flow["page_size"] = page_size
            user_state.show_page_flow["total_pages"] = total_pages

            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(pages))
            current_pages = pages[start_idx:end_idx]

            # Create simple page list
            page_items = []
            __process_paging(page_items, current_pages, start_idx, collection_user_id)

            # Prepare card components
            card_body = [
                {
                    "type": AdaptiveCardConst.TEXT_BLOCK,
                    "text": f"📚 Pages in {collection_name}",
                    "weight": "Bolder",
                    "size": "Medium",
                },
            ]

            # Add search container
            search_container = create_search_container(
                "Search by page name or ID...",
                search_text,
                "apply_search",
                selected_source,
            )
            card_body.append(search_container)

            # Add filter info if filtering is active
            if search_text:
                extension = {"sourceSelection": selected_source}
                filter_info = create_filter_info(
                    len(pages),
                    len(all_pages),
                    search_text,
                    "clear_search",
                    **extension,
                )
                card_body.append(filter_info)

            # Add pagination info
            card_body.extend(
                [
                    {
                        "type": AdaptiveCardConst.TEXT_BLOCK,
                        "text": f"Showing {start_idx + 1}-{end_idx} of {len(pages)} pages",
                        "wrap": True,
                    },
                    {
                        "type": AdaptiveCardConst.TEXT_BLOCK,
                        "text": f"Page {current_page} of {total_pages}",
                        "horizontalAlignment": "Center",
                        "weight": "Bolder",
                        "color": AdaptiveCardConst.COLOR_ACCENT,
                        "spacing": "Small",
                    },
                ],
            )

            # Add page items
            card_body.extend(page_items)

            # Create pagination buttons
            actions = []
            if total_pages > 1:
                if current_page > 1:
                    actions.append(
                        {
                            "type": AdaptiveCardConst.ACTION_SUBMIT,
                            "title": "Previous",
                            "data": {"action": "show_page_prev_page"},
                        },
                    )
                if current_page < total_pages:
                    actions.append(
                        {
                            "type": AdaptiveCardConst.ACTION_SUBMIT,
                            "title": "Next",
                            "data": {"action": "show_page_next_page"},
                        },
                    )

            # Create the card content
            card_content = create_basic_card(
                title="",
                body_items=card_body,
                actions=actions,
                version=AdaptiveCardConst.CARD_VERSION_1_3,
            )

            # Send or update the card
            if is_update and user_state.show_page_flow.get("message_id"):
                # Update existing activity
                update_activity = MessageFactory.attachment(
                    Attachment(
                        content_type=AdaptiveCardConst.CONTENT_TYPE,
                        content=card_content,
                    ),
                )
                update_activity.id = user_state.show_page_flow["message_id"]
                await context.update_activity(update_activity)
            else:
                # Send new activity
                response = await context.send_activity(
                    MessageFactory.attachment(
                        Attachment(
                            content_type=AdaptiveCardConst.CONTENT_TYPE,
                            content=card_content,
                        ),
                    ),
                )
                if response is not None and hasattr(response, "id"):
                    user_state.show_page_flow["message_id"] = response.id
            return

        except Exception as e:
            card = create_error_card(
                title="❌ Error Retrieving Pages",
                message=f"Error: {e!s}",
            )
            await send_adaptive_card(context, card)


async def process_selected_pages_deletion_request(context: TurnContext, state: AppTurnState) -> None:
    """Show confirmation dialog for deleting selected pages."""
    user_state = getattr(state, "user", state)

    if not hasattr(context.activity, "value") or not isinstance(context.activity.value, dict):
        return
    form_data = context.activity.value
    source_pages_map = user_state.remove_page_flow.get("source_pages_map", {})

    # Start with persisted selections (ids or dicts)
    all_pages = user_state.remove_page_flow.get("all_pages", []) or []
    persisted = user_state.remove_page_flow.get("selected_pages", []) or []
    persisted_map = {}
    for p in persisted:
        if isinstance(p, dict):
            pid = str(p.get("id") or p.get("page_id") or p.get("id"))
            persisted_map[pid] = dict(p)
        else:
            persisted_map[str(p)] = {"id": str(p), "page_id": str(p), "name": "", "source_id": ""}

    # Enrich persisted entries with metadata from all_pages
    try:
        for pid, record in list(persisted_map.items()):
            if not record.get("name") or not record.get("source_id"):
                for ap in all_pages:
                    if str(ap.get("id")) == str(pid) or str(ap.get("page_id")) == str(pid):
                        record["id"] = str(ap.get("id") or pid)
                        record["page_id"] = ap.get("identity_constant_name") or ap.get("page_id") or record.get("page_id")
                        record["name"] = ap.get("name") or ap.get("page_name") or record.get("name")
                        record["source_id"] = ap.get("_source_id") or ap.get("collection_id") or record.get("source_id")
                        record["source_type"] = ap.get("source_type") or record.get("source_type")
                        persisted_map[pid] = record
                        break
    except Exception:
        pass

    # Merge current form toggles
    for key, value in (form_data or {}).items():
        if key.startswith("page_"):
            page_id = key.replace("page_", "")
            if str(value).lower() == "true":
                # find page metadata in all_pages first, then fallback to source_pages_map
                found = False
                for page in all_pages:
                    if str(page.get("id")) == str(page_id) or str(page.get("page_id")) == str(page_id):
                        persisted_map[str(page_id)] = {
                            "id": str(page_id),
                            "page_id": page.get("identity_constant_name") or page.get("page_id") or str(page_id),
                            "name": page.get("name", page.get("page_name", page_id)),
                            "source_id": page.get("_source_id") or page.get("collection_id") or "",
                            "source_type": page.get("source_type"),
                        }
                        found = True
                        break
                if not found:
                    for source_id, pages in source_pages_map.items():
                        for page in pages:
                            if str(page.get("id")) == str(page_id):
                                persisted_map[str(page_id)] = {
                                    "id": str(page_id),
                                    "page_id": page.get("identity_constant_name") or page.get("page_id") or str(page_id),
                                    "name": page.get("name", page_id),
                                    "source_id": source_id,
                                    "source_type": page.get("source_type"),
                                }
                                found = True
                                break
                        if found:
                            break
                if not found:
                    persisted_map[str(page_id)] = {"id": str(page_id), "page_id": str(page_id), "name": "", "source_id": ""}
            else:
                persisted_map.pop(str(page_id), None)

    selected_pages = list(persisted_map.values())
    if not selected_pages:
        card = create_error_card(
            title="⚠️ No Pages Selected",
            message="Please select at least one page to remove.",
        )
        await send_adaptive_card(context, card)
        return
    # persist merged selections
    user_state.remove_page_flow["selected_pages"] = selected_pages
    num_pages = len(selected_pages)
    plural = "s" if num_pages > 1 else ""
    sources = set(page["source_id"] for page in selected_pages)
    plural_sources = "s" if len(sources) > 1 else ""
    source_names_map = user_state.remove_page_flow.get("source_names_map", {})

    # Ensure we show readable source/collection names in the confirmation.
    # If map is missing entries, try to fetch from DB; otherwise fall back to page metadata stored in all_pages
    try:
        missing_ids = [str(sid) for sid in sources if str(sid) not in source_names_map]
        if missing_ids:
            # Try to query DB with integer IDs when possible
            int_ids = []
            for mid in missing_ids:
                try:
                    int_ids.append(int(mid))
                except ValueError:
                    # skip non-integer ids
                    continue
            collections = []
            if int_ids:
                collections = Collection.find_by_filter(id__in=int_ids) or []
            # If DB query didn't return results, fall back to scanning all collections
            if not collections:
                try:
                    all_cols = Collection.find_all() or []
                    for c in all_cols:
                        cid = str(c.id)
                        if cid in missing_ids:
                            source_names_map[cid] = c.name
                except Exception as e:
                    # best-effort: ignore DB errors here but keep a debug trace for troubleshooting
                    _logger.debug("Failed to fetch all collections for missing source names: %s", e, exc_info=True)
            else:
                for c in collections:
                    source_names_map[str(c.id)] = c.name
            user_state.remove_page_flow["source_names_map"] = source_names_map
    except Exception as e:
        # non-fatal; continue with best-effort names — keep a debug trace for investigation when needed
        _logger.debug("Error while resolving source names for confirmation: %s", e, exc_info=True)

    # Also seed names from per-page metadata if available
    for page in selected_pages:
        sid = str(page.get("source_id") or "")
        if sid and sid not in source_names_map:
            candidate = page.get("_source_name") or page.get("source_name")
            if candidate:
                source_names_map[sid] = candidate

    message = f"Are you sure you want to remove {num_pages} selected page{plural} from {len(sources)} knowledge base{plural_sources}?"
    message += "\n\nSelected pages:"
    for source_id in sources:
        source_pages = [page for page in selected_pages if page.get("source_id") == source_id]
        sid = str(source_id)
        source_name = source_names_map.get(sid) or next((p.get("_source_name") or p.get("source_name") for p in source_pages if p), sid)
        message += f"\n\n📚 {source_name}:"
        for page in source_pages:
            message += f"\n- {page.get('name') or page.get('page_id') or page.get('id')}"
    # Create a confirmation snapshot and an id so the confirm action will
    # operate on an immutable snapshot even if the user changes selections
    # afterwards.
    confirm_id = str(uuid4())
    pending = user_state.remove_page_flow.setdefault("pending_confirmations", {})
    pending[confirm_id] = selected_pages.copy()
    confirmation_card = create_confirmation_dialog(
        title="⚠️ Confirm Pages Deletion",
        message=message,
        confirm_action="remove_selected_pages_confirm",
        is_destructive=True,
    )
    
    try:
        actions = confirmation_card.get("actions", [])
        if actions:
            actions[0].setdefault("data", {})["confirm_id"] = confirm_id

        # Also add a hidden input to the card body to ensure the confirm_id
        # is included in the submitted activity payload across clients.
        body = confirmation_card.get("body", [])
        body.append({
            "type": "Input.Text",
            "id": "confirm_id",
            "value": confirm_id,
            "isVisible": False,
        })
        confirmation_card["body"] = body
    except Exception:
        _logger.exception("Failed to attach confirm_id to confirmation card")

    await context.send_activity(
        MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=confirmation_card)),
    )


async def process_selected_pages_removal(context: TurnContext, state: AppTurnState) -> None:
    """Process deletion of selected pages after confirmation."""
    user_state = getattr(state, "user", state)
    # Determine which confirmation snapshot to use. The confirm button should
    # include a confirm_id in the submitted payload. Use that to pop the
    # corresponding snapshot. If missing, fall back to the older single-snapshot
    # behavior for backward compatibility.
    form_data = context.activity.value if hasattr(context.activity, "value") else {}
    confirm_id = form_data.get("confirm_id") if isinstance(form_data, dict) else None

    # Debug: log the form data and pending confirmations keys
    try:
        _logger.debug(f"Confirm removal invoked. form_data keys: {list(form_data.keys()) if isinstance(form_data, dict) else form_data}")
        _logger.debug(f"Pending confirmations keys: {list(user_state.remove_page_flow.get('pending_confirmations', {}).keys())}")
    except Exception:
        pass

    selected_pages = None
    pending = user_state.remove_page_flow.get("pending_confirmations", {})
    if confirm_id:
        selected_pages = pending.pop(confirm_id, None)
        # clean up map if empty
        if not pending:
            user_state.remove_page_flow.pop("pending_confirmations", None)
    else:
        # If no confirm_id provided but there is exactly one pending snapshot,
        # use it for backward compatibility. If there are multiple pending
        # confirmations, abort to avoid ambiguity.
        if len(pending) == 1:
            # pop the only item
            only_id = next(iter(pending))
            selected_pages = pending.pop(only_id)
            user_state.remove_page_flow.pop("pending_confirmations", None)
        elif len(pending) > 1:
            await context.send_activity(
                (
                    "❌ Ambiguous confirmation: multiple pending operations exist. "
                    "Please retry the removal from the pages view."
                ),
            )
            return
        else:
            # No pending confirmations: fall back to current selected_pages
            selected_pages = user_state.remove_page_flow.get("selected_pages", [])
    if not selected_pages:
        await context.send_activity(
            MessageFactory.attachment(
                Attachment(
                    content_type=AdaptiveCardConst.CONTENT_TYPE,
                    content={
                        "type": "AdaptiveCard",
                        "version":AdaptiveCardConst.CARD_VERSION_1_3,
                        "body": [
                            {"type":AdaptiveCardConst.TEXT_BLOCK, "text": "⚠️ No Pages Selected", "weight": "Bolder", "size": "Medium", "color": "Warning"},
                            {"type":AdaptiveCardConst.TEXT_BLOCK, "text": "No pages were selected for removal.", "wrap": True},
                        ],
                    },
                ),
            ),
        )
        return
    # Debug: log which snapshot we are about to process
    try:
        _logger.debug(f"Processing confirmed removal for confirm_id={confirm_id}; pages={[(p.get('id'), p.get('name')) for p in selected_pages]}")
    except Exception:
        pass
    await __send_typing_indicator(context)
    pages_by_source = {}
    for page in selected_pages:
        source_id = page["source_id"]
        if source_id not in pages_by_source:
            pages_by_source[source_id] = []
        pages_by_source[source_id].append(page)

    all_sources = Collection.find_all()
    source_names_map = {str(source.id): str(source.name) for source in all_sources}
    user_state.remove_page_flow["source_names_map"] = source_names_map
    total_success = 0
    failed_pages = []
    # Track successfully deleted page ids per source to correctly update the view
    deleted_ids_by_source: dict[str, set[str]] = {}
    # Also track external identity ids (identity_constant_name / page_id) that were deleted
    deleted_external_ids_by_source: dict[str, set[str]] = {}
    try:
        source_names_map = user_state.remove_page_flow.get("source_names_map", {})
        # Ensure each selected page has source_id and page_id resolved by scanning source_pages_map
        source_pages_map = user_state.remove_page_flow.get("source_pages_map", {})
        for sel in selected_pages:
            if not sel.get("source_id") or not sel.get("page_id"):
                # attempt to find in source_pages_map
                for src_id, pages in source_pages_map.items():
                    for p in pages:
                        if str(p.get("id")) == str(sel.get("id")) or str(p.get("page_id")) == str(sel.get("id")):
                            sel.setdefault("source_id", src_id)
                            sel.setdefault("page_id", p.get("identity_constant_name") or p.get("page_id") or p.get("id"))
                            sel.setdefault("name", p.get("name") or p.get("page_name") or sel.get("name", ""))
                            sel.setdefault("source_type", p.get("source_type"))
                            break
                    if sel.get("source_id"):
                        break
        for source_id, pages in pages_by_source.items():
            _logger.debug("processing source_id: %s, pages: %s", source_id, pages)
            source_name = source_names_map.get(str(source_id), str(source_id))
            if source_name:
                for page in pages:
                    # Use the external identity (page_id or identity_constant_name) when requesting deletion
                    external_page_id = str(page.get("page_id") or page.get("identity_constant_name") or page.get("id"))
                    source_type = page.get("source_type")
                    not_found_ids = await ManageSource.delete_pages_for_source(
                        collection_id=source_id,
                        page_ids=[external_page_id],
                        source_type=SourceType.CONFLUENCE if source_type == "CONFLUENCE" else SourceType.GCP,
                    )
                    # Normalize not_found_ids to strings for safe comparison
                    not_found_set = {str(x) for x in (not_found_ids or [])}
                    # The delete_pages_for_source returns identity_constant_name values that were NOT found.
                    if external_page_id in not_found_set:
                        failed_pages.append(page)
                    else:
                        total_success += 1
                        deleted_ids_by_source.setdefault(str(source_id), set()).add(str(page.get("id")))
                        deleted_external_ids_by_source.setdefault(str(source_id), set()).add(external_page_id)
            else:
                failed_pages.extend(pages)
        user_state.remove_page_flow["selected_pages"] = []
        if total_success > 0:
            success_msg = f"✅ Successfully removed {total_success} page{'s' if total_success > 1 else ''}"
            if failed_pages:
                success_msg += f"\n❌ Failed to remove {len(failed_pages)} page{'s' if len(failed_pages) > 1 else ''}"
                for page in failed_pages:
                    source_name = source_names_map.get(str(page["source_id"]), str(page["source_id"]))
                    success_msg += f"\n- {page['name']} (ID: {page['id']}) from {source_name}"

            card = create_success_card(
                title="✅ Pages Removed Successfully",
                message=success_msg,
            )
            await send_adaptive_card(context, card)
            source_pages_map = user_state.remove_page_flow.get("source_pages_map", {})
            updated_source_pages_map = {}
            for source_id, pages in source_pages_map.items():
                deleted_ids = deleted_ids_by_source.get(str(source_id), set())
                remaining_pages = [p for p in pages if str(p.get("id")) not in deleted_ids]
                if remaining_pages:
                    updated_source_pages_map[source_id] = remaining_pages
            user_state.remove_page_flow["source_pages_map"] = updated_source_pages_map
            try:
                pending = user_state.remove_page_flow.get("pending_confirmations", {})
                if pending and (deleted_ids_by_source or deleted_external_ids_by_source):
                    # flatten deleted DB ids and external ids
                    all_deleted_db_ids = {did for s in deleted_ids_by_source.values() for did in s}
                    all_deleted_external_ids = {eid for s in deleted_external_ids_by_source.values() for eid in s}
                    to_delete_confirm_ids = []
                    for pid, pages_snapshot in list(pending.items()):
                        # Remove any pages that were deleted either by DB id or by external id
                        def _is_deleted(p: dict) -> bool:
                            if str(p.get("id")) in all_deleted_db_ids:
                                return True
                            ext = str(p.get("page_id") or p.get("identity_constant_name") or "")
                            if ext and ext in all_deleted_external_ids:
                                return True
                            return False

                        new_snapshot = [p for p in pages_snapshot if not _is_deleted(p)]
                        if new_snapshot:
                            pending[pid] = new_snapshot
                        else:
                            # snapshot became empty, remove it
                            to_delete_confirm_ids.append(pid)
                    for pid in to_delete_confirm_ids:
                        pending.pop(pid, None)
                    # persist changes
                    if pending:
                        user_state.remove_page_flow["pending_confirmations"] = pending
                    else:
                        user_state.remove_page_flow.pop("pending_confirmations", None)
            except Exception:
                # don't let cleanup failures block the response
                _logger.exception("Failed to cleanup pending confirmations after deletion")
            # Recompute flattened all_pages and pagination so the pages view
            # reflects the updated data and preserves pagination state.
            all_pages = []
            for pages in updated_source_pages_map.values():
                if pages and isinstance(pages, list):
                    all_pages.extend(pages)
            user_state.remove_page_flow["all_pages"] = all_pages

            # Preserve page_size if present, default to 20
            page_size = user_state.remove_page_flow.get("page_size", 20) or 20
            try:
                total_pages = (len(all_pages) + int(page_size) - 1) // int(page_size) if int(page_size) > 0 else 1
            except Exception:
                total_pages = 1
            user_state.remove_page_flow["total_pages"] = total_pages

            # Clamp current_page to the new total_pages
            current_page = user_state.remove_page_flow.get("current_page", 1) or 1
            try:
                current_page = int(current_page)
            except Exception:
                current_page = 1
            if current_page > total_pages:
                current_page = total_pages
            if current_page < 1:
                current_page = 1
            user_state.remove_page_flow["current_page"] = current_page

            # Refresh the pages view using the paginated navigator so the
            # current page and page size are preserved instead of rendering
            # the full unpaged list which caused the card to "change form".
            # Pass the full AppTurnState (`state`) so the navigator can derive
            # the `user` state and access `remove_page_flow` correctly.
            await navigate_remove_pages(context, state, 0)
        else:
            await context.send_activity("❌ Failed to remove any selected pages.")
    except Exception as e:
        card = create_error_card(
            title="❌ Error Removing Pages",
            message=f"An error occurred while removing pages: {e!s}",
        )
        await send_adaptive_card(context, card)


async def __update_pages_view(context: TurnContext, state: AppTurnState, source_pages_map: dict) -> None:
    """Updates the pages view card with multiple selection support."""
    user_state = getattr(state, "user", state)
    # Create updated card
    source_names_map = user_state.remove_page_flow.get("source_names_map", {})
    try:
        total_count = sum(len(pages) for pages in user_state.remove_page_flow.get("source_pages_map", {}).values())
    except Exception:
        total_count = None
    card = create_pages_by_source_card(
        source_pages_map,
        selected_pages=user_state.remove_page_flow.get("selected_pages", []),
        source_names_map=source_names_map,
        total_count=total_count,
    )

    # Create message
    update_activity = MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card))

    # Update existing card if we have a message ID
    message_id = user_state.remove_page_flow.get("message_id")
    if message_id:
        update_activity.id = message_id
        await context.update_activity(update_activity)
    else:
        # Otherwise send as new message message
        response = await context.send_activity(update_activity)
        if response is not None and hasattr(response, "id"):
            user_state.remove_page_flow["message_id"] = response.id


async def __fetch_pages_for_source(source_id) -> tuple:
    """Fetch pages for a given source ID and return them along with the collection name and user_id."""
    collection = Collection.find_by_filter(id=source_id)
    if not collection:
        raise ValueError(f"Source {source_id} not found")
    collection_model = collection[0]
    collection_name = collection_model.name
    collection_user_id = collection_model.user_id
    pages = []
    confluence_pages = __fetch_confluence_pages(source_id)
    gcp_pages = __fetch_gcp_pages(source_id)
    pages.extend(confluence_pages)
    pages.extend(gcp_pages)
    if not pages:
        vector_pages = __fetch_vector_pages(source_id)
        pages = vector_pages
    pages = __normalize_pages(pages)
    return pages, collection_name, collection_user_id


def __fetch_confluence_pages(source_id) -> list:
    return (
        ManageSource.fetch_confluence_pages_metadata(collection_id=source_id, source_type=SourceType.CONFLUENCE) or []
    )


def __fetch_gcp_pages(source_id) -> list:
    pages = ManageSource.fetch_confluence_pages_metadata(collection_id=source_id, source_type=SourceType.GCP) or []
    return pages


def __fetch_vector_pages(source_id) -> list:
    try:
        vector_pages = ManageSource.fetch_pages_in_source(source_id)
        pages = []
        if vector_pages:
            for source_data in vector_pages:
                for page_name in source_data.get("pages", []):
                    pages.append(
                        {
                            "page_id": page_name,
                            "id": page_name,
                            "collection_id": source_id,
                            "page_name": page_name,
                            "name": page_name,
                            "version": "1",
                            "created_date": None,
                            "updated_date": None,
                            "source_path": "",
                            "source_type": "CONFLUENCE",
                            "public_url": None,
                        },
                    )
        return pages
    except Exception:
        return []


def __normalize_pages(pages) -> list:
    for page in pages:
        if not page.get("name"):
            page["name"] = page.get("page_name", "Untitled Page")
        if not page.get("id"):
            page["id"] = page.get("page_id", "")
    return pages


def __format_updated_date(updated_date):
    if not updated_date or updated_date == UNKNOWN_DATE:
        return UNKNOWN_DATE
    try:
        if isinstance(updated_date, str):
            iso_string = updated_date.replace("Z", "+00:00") if updated_date.endswith("Z") else updated_date
            dt = datetime.fromisoformat(iso_string)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return updated_date.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(updated_date)


def __create_action_button(is_user_source: bool, page: dict, page_id: str, page_name: str, source_type: str) -> list | dict:
    url = page.get("public_url")
    if not url and source_type == "CONFLUENCE":
        source_path = (page.get("source_path") or "").strip()
        # Only attempt to build a pageId-based Confluence URL when page_id is numeric
        if source_path and page_id and str(page_id).isdigit():
            sp = source_path
            parsed_sp = urlparse(sp)
            # If there's no scheme, default to https
            if not parsed_sp.scheme:
                sp = "https://" + sp.lstrip("/")
            # If the stored path already contains pages/viewpage.action, use it or append pageId
            if "pages/viewpage.action" in sp:
                url = sp if "pageId=" in sp else sp.rstrip("/") + f"?pageId={page_id}"
            else:
                parsed = urlparse(sp)
                if "atlassian.net" in (parsed.netloc or "") and not (parsed.path or "").startswith("/wiki"):
                    url = sp.rstrip("/") + f"/wiki/pages/viewpage.action?pageId={page_id}"
                else:
                    url = sp.rstrip("/") + f"/pages/viewpage.action?pageId={page_id}"
    actions = []
    if url:
        url, _ = url_shortening_service.shorten_url(url)
        actions.append({"type": AdaptiveCardConst.ACTION_OPEN_URL, "title": "View", "url": url})

    # Always include Remove when user owns the source, otherwise only View may be shown
    if is_user_source:
        actions.append(
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "Remove",
                "data": {
                    "action": "remove_page_delete_request",
                    "pageId": page_id,
                    "pageName": page_name,
                    "sourceType": source_type,
                    "sourceId": page.get("collection_id", ""),
                },
            },
        )

    # Return single action if only one, else list
    if len(actions) == 1:
        return actions[0]
    return actions


def __process_paging(page_items: list, pages: list, start_idx: int, collection_user_id: str | None = None) -> None:
    for i, page in enumerate(pages, start=start_idx + 1):
        page_name = page.get("page_name") or UNTITLE_PAGE
        page_id = page.get("page_id") or ""
        source_type = page.get("source_type") or ""
        updated_date = page.get("updated_date") or UNKNOWN_DATE
        updated_date_str = __format_updated_date(updated_date)
        action_button = __create_action_button(bool(collection_user_id), page, page_id, page_name, source_type)
        # Only append dicts to page_items
        page_items.append(
            {
                "type": AdaptiveCardConst.CONTAINER,
                "style": "emphasis",
                "items": [
                    {
                        "type": AdaptiveCardConst.COLUMN_SET,
                        "columns": [
                            {
                                "type": AdaptiveCardConst.COLUMN,
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": AdaptiveCardConst.TEXT_BLOCK,
                                        "text": f"{i}. {page_name}",
                                        "weight": "Bolder",
                                        "wrap": True,
                                    },
                                    {
                                        "type": AdaptiveCardConst.TEXT_BLOCK,
                                        "text": f"ID: {page_id}",
                                        "size": "Small",
                                        "spacing": "None",
                                        "isSubtle": True,
                                    },
                                    {
                                        "type": AdaptiveCardConst.TEXT_BLOCK,
                                        "text": f"Updated: {updated_date_str}",
                                        "size": "Small",
                                        "spacing": "None",
                                        "isSubtle": True,
                                    },
                                ],
                            },
                            {
                                "type": AdaptiveCardConst.COLUMN,
                                "width": "auto",
                                "items": [
                                    {
                                        "type": AdaptiveCardConst.ACTION_SET,
                                        "actions": action_button
                                        if isinstance(action_button, list)
                                        else [action_button],
                                    },
                                ],
                                "verticalContentAlignment": "Center",
                            },
                        ],
                    },
                ],
                "spacing": "Small",
            },
        )


async def navigate_remove_pages(context: TurnContext, state: AppTurnState, direction: int) -> None:
    """Handles pagination for remove pages view.

    Args:
        context: Turn context
        state: AppTurnState containing user state and remove_page_flow information
        direction: Direction to navigate (1 for next, -1 for previous, 0 for refresh)

    """
    user_state = getattr(state, "user", state)
    remove_page_flow = user_state.remove_page_flow
    # Merge any incoming form toggles (from the current card submit) into persisted selections
    try:
        form_data = context.activity.value or {}
        if isinstance(form_data, dict):
            # collect page toggles
            persisted = remove_page_flow.get("selected_pages", [])
            # normalize persisted to a set of ids (support dict entries with multiple id fields)
            persisted_ids = set()
            for p in persisted:
                if isinstance(p, dict):
                    for k in ("id", "page_id", "pageId", "identity_constant_name"):
                        v = p.get(k)
                        if v is not None and str(v) != "":
                            persisted_ids.add(str(v))
                else:
                    persisted_ids.add(str(p))
            # Merge toggles
            for k, v in form_data.items():
                if k.startswith("page_"):
                    pid = k.replace("page_", "")
                    if str(v).lower() == "true":
                        if pid not in persisted_ids:
                            # store minimal dict with id only; source will be resolved later
                            persisted.append({"id": pid, "page_id": pid, "name": "", "source_id": ""})
                            persisted_ids.add(pid)
                    else:
                        # remove if exists: compare against multiple identifier fields
                        def _matches(p_item, target):
                            if isinstance(p_item, dict):
                                for k in ("id", "page_id", "pageId", "identity_constant_name"):
                                    v = p_item.get(k)
                                    if v is not None and str(v) == target:
                                        return True
                                return False
                            return str(p_item) == target

                        persisted = [p for p in persisted if not _matches(p, pid)]
                        # Remove any matching values from persisted_ids set
                        persisted_ids = {x for x in persisted_ids if x != pid}
            remove_page_flow["selected_pages"] = persisted
    except Exception:
        pass
    pages = remove_page_flow.get("all_pages", [])
    page_size = remove_page_flow.get("page_size", 10)
    total_pages = remove_page_flow.get("total_pages", 1)
    current_page = remove_page_flow.get("current_page", 1)

    # Update current page based on direction
    new_page = current_page + direction
    if new_page < 1:
        new_page = 1
    elif new_page > total_pages:
        new_page = total_pages

    remove_page_flow["current_page"] = new_page

    # Calculate page slice
    start_idx = (new_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(pages))
    current_pages = pages[start_idx:end_idx]

    # Update source pages map
    source_pages_map = {}
    for source_name, source_pages in remove_page_flow.get("source_pages_map", {}).items():
        source_pages_map[source_name] = current_pages

    # Create and send updated card
    source_names_map = remove_page_flow.get("source_names_map", {})
    try:
        total_count = sum(len(pages) for pages in remove_page_flow.get("source_pages_map", {}).values())
    except Exception:
        total_count = None
    card = create_pages_by_source_card(
        source_pages_map,
        selected_pages=remove_page_flow.get("selected_pages", []),
        source_names_map=source_names_map,
        total_count=total_count,
    )

    # Insert pagination header info at top of card body
    showing_text = {
        "type":AdaptiveCardConst.TEXT_BLOCK,
        "text": f"Showing {start_idx + 1}-{end_idx} of {len(pages)} pages",
        "wrap": True,
    }
    page_indicator = {
        "type":AdaptiveCardConst.TEXT_BLOCK,
        "text": f"Page {new_page} of {total_pages}",
        "horizontalAlignment": "Center",
        "weight": "Bolder",
        "color": "Accent",
        "spacing": "Small",
    }
    # Prepend header items so they appear above the page list
    card_body = card.get("body", [])
    card_body.insert(0, page_indicator)
    card_body.insert(0, showing_text)
    card["body"] = card_body

    # Ensure navigation actions exist
    actions = card.get("actions", []) or []
    nav_actions = []
    if total_pages > 1:
        if new_page > 1:
            nav_actions.append({"type": AdaptiveCardConst.ACTION_SUBMIT, "title": "Previous", "data": {"action": "remove_page_prev_page"}})
        if new_page < total_pages:
            nav_actions.append({"type": AdaptiveCardConst.ACTION_SUBMIT, "title": "Next", "data": {"action": "remove_page_next_page"}})

    # Merge navigation actions before existing actions
    card["actions"] = nav_actions + actions

    # Update existing card if we have a message ID
    message_id = remove_page_flow.get("message_id")
    # If message_id was set previously and the user is re-opening view, ensure we create a new activity
    # (avoid updating an old card buried in the chat). If caller set a flag 'force_new' in flow, clear message_id.
    if remove_page_flow.get("force_new_message"):
        message_id = None
        remove_page_flow.pop("message_id", None)
        remove_page_flow.pop("force_new_message", None)
    if message_id:
        update_activity = MessageFactory.attachment(
            Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card),
        )
        update_activity.id = message_id
        await context.update_activity(update_activity)
    else:
        # Otherwise send as new message
        response = await context.send_activity(
            MessageFactory.attachment(Attachment(content_type=AdaptiveCardConst.CONTENT_TYPE, content=card)),
        )
        if response is not None and hasattr(response, "id"):
            remove_page_flow["message_id"] = response.id


async def process_remove_entire_source_request(context: TurnContext, state: AppTurnState) -> None:
    """Show confirmation dialog for removing an entire source."""
    user_state = getattr(state, "user", state)
    if not hasattr(context.activity, "value") or not isinstance(context.activity.value, dict):
        return

    source_id = context.activity.value.get("sourceId")
    source_name = context.activity.value.get("sourceName")
    if not source_id or not source_name:
        return

    # Store source info for deletion
    user_state.remove_page_flow["source_id"] = source_id
    user_state.remove_page_flow["source_name"] = source_name

    # Create confirmation dialog
    confirmation_card = create_confirmation_dialog(
        title="⚠️ Confirm Source Removal",
        message=f"Are you sure you want to remove the entire knowledge base '{source_name}'? This action cannot be undone.",
        confirm_action="remove_entire_source_confirm",
        is_destructive=True,
    )

    await send_adaptive_card(context, confirmation_card)


async def process_remove_entire_source(context: TurnContext, state: AppTurnState) -> None:
    """Process the removal of an entire source after confirmation."""
    user_state = getattr(state, "user", state)
    source_id = user_state.remove_page_flow.get("source_id")
    source_name = user_state.remove_page_flow.get("source_name")

    if not source_id:
        return

    await __send_typing_indicator(context)

    try:
        # Delete the entire collection
        await ManageSource.aremove_source(source_id)

        # Send success message
        card = create_success_card(
            title="✅ Knowledge Base Removed Successfully",
            message=f"The knowledge base '{source_name}' has been completely removed.",
        )
        await send_adaptive_card(context, card)
        return

    except Exception as e:
        card = create_error_card(
            title="❌ Failed to Remove Knowledge Base",
            message=f"Error: {e!s}",
        )
        await send_adaptive_card(context, card)
        _logger.error("Error removing source: %s", e, exc_info=True)
        return


async def process_remove_multiple_sources_request(
    context: TurnContext,
    state: AppTurnState,
) -> None:
    """Process the removal of multiple sources."""
    user_state = getattr(state, "user", state)
    if not hasattr(context.activity, "value") or not isinstance(context.activity.value, dict):
        return
    form_data = context.activity.value
    selected_sources = []

    if not hasattr(user_state, "remove_page_flow"):
        user_state.remove_page_flow = {}

    # Process all keys in form_data
    for key, value in form_data.items():
        if key.startswith("source_") and value == "true":
            source_id = key.replace("source_", "")
            selected_sources.append(source_id)

    source_names_map = user_state.remove_page_flow.get("source_names_map", {})
    # Fix: If source_names_map is missing or incomplete, fetch names from DB
    missing_ids = [sid for sid in selected_sources if sid not in source_names_map]
    if missing_ids:
        collections = Collection.find_by_filter(id__in=missing_ids)  # Use id__in for list
        for c in collections:
            source_names_map[str(c.id)] = c.name
        user_state.remove_page_flow["source_names_map"] = source_names_map
    # End Fix
    if not selected_sources:
        await context.send_activity("⚠️ No sources selected for removal.")
        return

    # Get source names
    source_names = [source_names_map.get(sid, sid) for sid in selected_sources]
    # Store in state for confirmation
    user_state.remove_page_flow["selected_sources_to_remove"] = selected_sources

    # Create confirmation message
    message = "Are you sure you want to remove the following knowledge bases?\n\n"
    for name in source_names:
        message += f"- {name}\n"
    # Create confirmation card
    confirmation_card = create_confirmation_dialog(
        title="⚠️ Confirm Multiple Source Removal",
        message=message,
        confirm_action="remove_multiple_sources_confirm",
        is_destructive=True,
    )

    await send_adaptive_card(context, confirmation_card)


async def process_remove_multiple_sources_removal(
    context: TurnContext,
    state: AppTurnState,
) -> None:
    """Process removal of multiple sources after confirmation."""
    user_state = getattr(state, "user", state)
    selected_sources = user_state.remove_page_flow.get("selected_sources_to_remove", [])
    source_names_map = user_state.remove_page_flow.get("source_names_map", {})
    if not selected_sources:
        await context.send_activity("No sources selected for removal.")
        return
    success = []
    failed = []
    for source_id in selected_sources:
        try:
            await ManageSource.aremove_source(source_id)
            success.append(source_names_map.get(source_id, source_id))
        except Exception as e:
            failed.append(f"{source_names_map.get(source_id, source_id)}: {e!s}")
    msg = ""
    if success:
        msg += f"✅ Removed: {', '.join(success)}\n"
    if failed:
        msg += f"❌ Failed: {'; '.join(failed)}"
    await context.send_activity(msg or "No sources were removed.")
    # Reset state
    user_state.remove_page_flow["selected_sources_to_remove"] = []
