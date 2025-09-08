
import logging
from urllib.parse import urlparse
from src.adaptive_cards.card_utils import create_action, create_basic_card, create_text_block
from src.constants.app_constants import AdaptiveCardConst
from src.services.rag_services.url_shortening_service import url_shortening_service

_logger = logging.getLogger(__name__)
PAGES_VIEW_ACTION = "pages/viewpage.action"


def _build_confluence_page_url(source_path: str | None, page_id: str) -> str | None:
    """Build a reasonable Confluence page URL from a stored source_path and page id.

    Centralized helper to reduce duplication.
    """
    if not source_path:
        return None
    sp = (source_path or "").strip()
    if not sp:
        return None
    parsed = urlparse(sp)
    if not parsed.scheme:
        sp = "https://" + sp.lstrip("/")
        parsed = urlparse(sp)

    if PAGES_VIEW_ACTION in sp:
        return sp if "pageId=" in sp else sp.rstrip("/") + f"?pageId={page_id}"

    if "atlassian.net" in (parsed.netloc or "") and not (parsed.path or "").startswith("/wiki"):
        return sp.rstrip("/") + f"/wiki/{PAGES_VIEW_ACTION}?pageId={page_id}"

    return sp.rstrip("/") + f"/{PAGES_VIEW_ACTION}?pageId={page_id}"


def create_search_container(placeholder: str, search_text: str, action_name: str, collection_id: str) -> dict:
    """Create search input container."""
    return {
        "type": AdaptiveCardConst.CONTAINER,
        "spacing": "Medium",
        "style": "emphasis",
        "bleed": True,
        "items": [
            {
                "type": AdaptiveCardConst.COLUMN_SET,
                "columns": [
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "stretch",
                        "items": [
                            {
                                "type": AdaptiveCardConst.INPUT_TEXT,
                                "id": "searchQuery",
                                "placeholder": placeholder,
                                "value": search_text,
                            },
                        ],
                    },
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "auto",
                        "items": [
                            {
                                "type": AdaptiveCardConst.ACTION_SET,
                                "actions": [
                                    {
                                        "type": AdaptiveCardConst.ACTION_SUBMIT,
                                        "title": "Search",
                                        "data": {
                                            "action": action_name,
                                            "sourceSelection": collection_id,
                                        },
                                    },
                                ],
                            },
                        ],
                        "verticalContentAlignment": "Center",
                    },
                ],
            },
        ],
    }


def create_source_pages_container(source_name: str, pages: list, selected_pages: list | None = None, is_user_source: bool = False) -> dict:
    """Create a container showing pages for a specific source.

    is_user_source is accepted to match other callers; referencing it avoids lint warnings.
    """

    source_container: dict = {
        "type": AdaptiveCardConst.CONTAINER,
        "style": "emphasis",
        "spacing": "Large",
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
                                "text": f"📚 {source_name}",
                                "weight": "Bolder",
                                "size": "Medium",
                            },
                        ],
                    },
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "auto",
                        "items": [
                            {
                                "type": AdaptiveCardConst.TEXT_BLOCK,
                                "text": f"{len(pages)} pages",
                                "size": "Small",
                                "wrap": True,
                            },
                        ],
                        "verticalContentAlignment": "Center",
                    },
                ],
            },
        ],
        "separator": True,
    }

    # Create pages container
    pages_container: dict = {"type": AdaptiveCardConst.CONTAINER, "spacing": "None", "items": []}
    # Normalize selected_pages to a set of ids (support list of ids or list of dicts)
    selected_ids = set()
    if selected_pages:
        for s in selected_pages:
            if isinstance(s, dict):
                sid = str(s.get("id") or s.get("page_id") or s.get("pageId") or "")
            else:
                sid = str(s)
            if sid:
                selected_ids.add(sid)

    for page in pages:
        # Use the Confluence page id when available (stored as 'page_id' from DB queries).
        # Fall back to 'id' (DB primary key) only if 'page_id' is missing.
        page_id = str(page.get("page_id", page.get("id", "")))
        page_name = page.get("name", page.get("page_name", "Untitled Page"))
        updated_date = page.get("updated_date", "Unknown date")
        source_type = page.get("source_type", "")
        public_url = page.get("public_url")
        if source_type == "GCP":
            source_type = "FILE"
            # For GCP files, public_url should already be set from data_source_metadata


        action_button = __create_action_button(page, page_id, source_type)

        # Add page item to container
        pages_container["items"].append(
            {
                "type": AdaptiveCardConst.COLUMN_SET,
                "columns": [
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "auto",
                        "items": [
                            {
                                "type": AdaptiveCardConst.INPUT_TOGGLE,
                                "id": f"page_{page_id}",
                                "value": str(page_id in selected_ids).lower(),
                                "spacing": "None",
                            },
                        ],
                        "verticalContentAlignment": "Center",
                    },
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "stretch",
                        "items": [
                            {
                                "type": AdaptiveCardConst.TEXT_BLOCK,
                                "text": page_name,
                                "wrap": True,
                                "weight": "Bolder",
                            },
                            {
                                "type": AdaptiveCardConst.TEXT_BLOCK,
                                "text": f"Updated: {updated_date}",
                                "size": "Small",
                                "isSubtle": True,
                                "spacing": "None",
                            },
                            {
                                "type": AdaptiveCardConst.TEXT_BLOCK,
                                "text": f"[{source_type}]",
                                "size": "Small",
                                "isSubtle": True,
                                "spacing": "None",
                                "weight": "Bolder",
                            },
                        ],
                    },
                    {
                        "type": AdaptiveCardConst.COLUMN,
                        "width": "auto",
                        "items": [
                            {
                                "type": AdaptiveCardConst.ACTION_SET,
                                "actions": [action_button],
                            },
                        ],
                        "verticalContentAlignment": "Center",
                    },
                ],
                "spacing": "Small",
            },
        )

    source_container["items"].append(pages_container)
    return source_container


def create_confirm_add_page_card(
    page_parent_id: str,
    page_parent_name: str,
    pages_child: list,
    sources: list,
) -> dict:
    """Create a confirmation card for adding a page.

    Args:
        page_parent_id (str): The ID of the parent page.
        page_parent_name (str): The name of the parent page.
        pages_child (list): A list of child pages to be added.
        sources (list): A list of available sources.

    Returns:
        dict: The created confirmation card.

    """
    default_source_id = sources[0]["id"] if sources and len(sources) > 0 else ""
    # Add a checkbox for each child page, and collect selected IDs
    child_page_toggles = []
    for page in pages_child:
        toggle_id = f"childPage_{page['id']}"
        child_page_toggles.append(
            {
                "type": AdaptiveCardConst.INPUT_TOGGLE,
                "id": toggle_id,
                "title": f"{page['title']} (ID: {page['id']})",
                "value": "true",
                "wrap": True,
                "isVisible": True,
            },
        )

    action_add_page = create_action(
        action_type=AdaptiveCardConst.ACTION_SUBMIT,
        title="✅ Confirm and Add Page",
        data={
            "action": "add_page_submit",
            "pageId": page_parent_id,
            "parentName": page_parent_name,
            "enableChildPages": "${enableChildPages}",
        },
    )
    return {
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_5,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "📄 Add Confluence Page to Knowledge Base",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Select knowledge base to add the page to:",
                "wrap": True,
            },
            {
                "type": AdaptiveCardConst.INPUT_CHOICE_SET,
                "id": "sourceSelection",
                "isRequired": True,
                "errorMessage": "Please select a knowledge base",
                "value": default_source_id,
                "choices": [{"title": str(source["name"]), "value": source["id"]} for source in sources],
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Page ID:",
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "id": "pageId",
                "text": page_parent_id,
                "wrap": True,
                "spacing": "None",
                "color": "Accent",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Page Title:",
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": page_parent_name,
                "wrap": True,
                "spacing": "None",
                "color": "Good",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Child pages will be added:",
                "wrap": True,
                "isVisible": bool(pages_child),
            },
            *child_page_toggles,
            {
                "type": AdaptiveCardConst.INPUT_TOGGLE,
                "id": "enableChildPages",
                "title": "Include child pages",
                "value": "True",
                "wrap": True,
                "isVisible": False,
            },
        ],
        "actions": [
            action_add_page,
        ],
        AdaptiveCardConst.SCHEMA_ATTRIBUTE: AdaptiveCardConst.SCHEMA,
    }


def create_remove_source_selection_card(sources: list) -> dict:
    """Create a card for removing source selection."""
    return {
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_3,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "🗑️ Remove from Knowledge Base",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Attention",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Select knowledge base to manage (you can select multiple):",
                "wrap": True,
            },
            {
                "type": AdaptiveCardConst.CONTAINER,
                "items": [
                    {
                        "type": AdaptiveCardConst.INPUT_TOGGLE,
                        "id": f"source_{source['id']}",  # Unique ID for each source toggle
                        "title": str(source["name"]),
                        "value": "false",  # Default to not selected
                        "wrap": True,
                        "labelPosition": "start",
                        "spacing": "medium",
                    }
                    for source in sources
                ],
                "spacing": "Medium",
                "style": "emphasis",
            },
        ],
        "actions": [
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "View Selected Knowledge Base",
                "data": {"action": "remove_page_source_selected", "sourcesData": sources},  # Store full source data
            },
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "Remove Selected Sources",
                "style": "destructive",
                "data": {
                    "action": "remove_selected_sources",
                    "sourcesData": sources,  # Store full source data
                    "isConfirmationRequired": True,
                },
            },
        ],
        AdaptiveCardConst.SCHEMA_ATTRIBUTE: AdaptiveCardConst.SCHEMA,
    }


def create_pages_by_source_card(
    source_pages_map: dict,
    selected_pages: list | None = None,
    source_names_map: dict | None = None,
    total_count: int | None = None,
) -> dict:
    """Create a card showing pages grouped by source with checkboxes for selection.

    Args:
        source_pages_map (dict): Dictionary mapping source IDs to their pages
        selected_pages (list, optional): List of selected page IDs
        source_names_map (dict, optional): Dictionary mapping source IDs to user_ids to determine source type

    """
    if selected_pages is None:
        selected_pages = []
    if source_names_map is None:
        source_names_map = {}

    card_body = [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "🗑️ Remove Pages from Knowledge Base",
            "weight": "Bolder",
            "size": "Medium",
            "color": "Attention",
        },
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "Select pages to remove from their knowledge base:",
            "wrap": True,
        },
    ]

    # Store total pages count across all sources. If caller provided an explicit total_count (for paged views), use it.
    total_pages = total_count if total_count is not None else sum(len(pages) for pages in source_pages_map.values())
    card_body.append(
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": f"Total pages across all knowledge base: {total_pages}",
            "wrap": True,
            "size": "Small",
            "isSubtle": True,
            "spacing": "Medium",
        },
    )

    # Add sections for each source
    for source_id, pages in source_pages_map.items():
        display_name = source_names_map.get(str(source_id), str(source_id))
        source_container = create_source_pages_container(display_name, pages, selected_pages)
        card_body.append(source_container)

    action = create_action(
        action_type=AdaptiveCardConst.ACTION_SUBMIT,
        title="Remove Selected Pages",
        data={"action": "remove_selected_pages", "isConfirmationRequired": True},
        style="destructive",
    )
    return create_basic_card(
        title="",
        body_items=card_body,
        actions=[action],
        version=AdaptiveCardConst.CARD_VERSION_1_3,
    )


def __create_action_button(page: dict, page_id: str, source_type: str) -> dict:
    """Create action button based on source type and user permissions."""
    public_url = page.get("public_url")
    if not public_url and source_type == "CONFLUENCE":
        # Build a sensible Confluence URL from stored source_path and page id
        public_url = _build_confluence_page_url(page.get("source_path"), page_id)

    if not public_url:
        # Fallback: no view URL available
        return create_action(
            action_type=AdaptiveCardConst.ACTION_OPEN_URL,
            title="View",
            url="#",
        )

    # Shorten the URL for presentation
    short_url, _ = url_shortening_service.shorten_url(str(public_url))

    return create_action(
        action_type=AdaptiveCardConst.ACTION_OPEN_URL,
        title="View",
        url=short_url,
    )


def select_source_page(
    user_sources: list[dict] | None,
    common_sources_list: list[dict] | None,
) -> dict:  # common_sources renamed to common_sources_list
    """Creates an adaptive card for selecting a knowledge source to view pages from.

    Ensures only one source can be selected across user and common sources.

    Args:
        user_sources: List of user-specific knowledge base sources (list of dicts)
        common_sources_list: List of common knowledge base sources (list of dicts)

    Returns:
        Adaptive card JSON object for source selection

    """
    body_elements = [
        {
            "type": AdaptiveCardConst.TEXT_BLOCK,
            "text": "Select which knowledge base you want to view pages from:",
            "wrap": True,
            "spacing": "Medium",  # Added spacing for better visual separation
        },
    ]

    all_display_choices = (
        [{"title": f"(Your) {s['name']!s}", "value": s["id"]} for s in (user_sources or [])]
        + [{"title": f"(Common) {s['name']!s}", "value": s["id"]} for s in (common_sources_list or [])]
    )
    final_default_value = ""
    if user_sources and len(user_sources) > 0:
        final_default_value = user_sources[0]["id"]
    elif common_sources_list and len(common_sources_list) > 0:
        final_default_value = common_sources_list[0]["id"]

    if all_display_choices:
        body_elements.append(
            {
                "type": AdaptiveCardConst.INPUT_CHOICE_SET,
                "id": "sourceSelection",  # Single ID for the combined choice set
                "style": "expanded",
                "isMultiSelect": False,
                "isRequired": True,  # A selection is required if choices are present
                "errorMessage": "Please select a knowledge base.",
                "value": final_default_value,  # Default to the first available option
                "choices": all_display_choices,
            },
        )
    else:
        # If no sources are available at all (this case might be handled before calling this function)
        body_elements.append(
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "No knowledge bases are currently available to select.",
                "wrap": True,
                "isSubtle": True,
            },
        )

    # Note on backend processing:
    # When this card is submitted, the selected value will be in `context.activity.value.sourceSelection`.
    # This single value represents the chosen knowledge base ID.

    action = create_action(
        action_type=AdaptiveCardConst.ACTION_SUBMIT,
        title="View Pages",
        data={"action": "show_page_source_selected"},
    )
    return create_basic_card(
        title="📚 View Knowledge Base Pages",
        body_items=body_elements,
        actions=[action],
        version=AdaptiveCardConst.CARD_VERSION_1_5,
    )


def create_source_selection_card(sources: list) -> dict:
    """Creates a source selection card for choosing a knowledge base."""
    # Set default selection if available
    default_source = sources[0]["id"] if sources and len(sources) > 0 else ""

    return {
        "type": "AdaptiveCard",
        "version": AdaptiveCardConst.CARD_VERSION_1_5,
        "body": [
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "📄 Add Confluence Page to Knowledge Base",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Select knowledge base to add the page to:",
                "wrap": True,
            },
            {
                "type": AdaptiveCardConst.INPUT_CHOICE_SET,
                "id": "sourceSelection",
                "isRequired": True,
                "errorMessage": "Please select a knowledge base",
                "value": default_source,
                "choices": [{"title": source["name"], "value": source["id"]} for source in sources],
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "Enter Confluence page ID:",
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": AdaptiveCardConst.INPUT_TEXT,
                "id": "pageId",
                "placeholder": "Example: 3377465353",
                "isRequired": True,
                "errorMessage": "Page ID is required",
            },
            {
                "type": AdaptiveCardConst.TEXT_BLOCK,
                "text": "💡 Tip: You can find the page ID in the Confluence page URL after 'pageId='",
                "wrap": True,
                "isSubtle": True,
                "size": "Small",
            },
            {
                "type": AdaptiveCardConst.INPUT_TOGGLE,
                "id": "enableAllChildPages",
                "title": "Include child pages",
                "value": "true",
                "wrap": True,
                "isVisible": True,
            },
        ],
        "actions": [
            {
                "type": AdaptiveCardConst.ACTION_SUBMIT,
                "title": "Add Page",
                "data": {"action": "add_page_submit", "enableAllChildPages": "${enableAllChildPages}"},
            },
        ],
        AdaptiveCardConst.SCHEMA_ATTRIBUTE: AdaptiveCardConst.SCHEMA,
    }


def create_confirmation_dialog(
    title: str,
    message: str,
    confirm_action: str,
    data_action: dict | None = None,
    is_destructive: bool = False,
) -> dict:
    """Creates a confirmation dialog with only the confirm option."""
    body_items = [create_text_block(message, wrap=True)]

    if is_destructive:
        body_items.append(
            create_text_block(
                "This action cannot be undone.",
                wrap=True,
                weight="Bolder",
            ),
        )

    data: dict = {"action": confirm_action}
    if data_action:
        data.update(data_action)
    # Create actions
    actions = [
        create_action(
            action_type=AdaptiveCardConst.ACTION_SUBMIT,
            title="Yes, Continue" if not is_destructive else "Yes, Delete",
            data=data,
            style="destructive" if is_destructive else None,
        ),
    ]

    return create_basic_card(title, body_items=body_items, actions=actions)
