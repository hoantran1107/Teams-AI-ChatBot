from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ExactActions:
    CANCEL_CONFLUENCE_COMMENT = "cancel_confluence_comment"
    CANCEL_COMMENT = "cancel_comment"
    """Exact actions for adaptive card."""

    SUBMIT_DRAFT = "submit_draft"
    ADD_PAGE_SUBMIT = "add_page_submit"
    NEW_CHAT = "new_chat"
    CLEAR_CHAT_HISTORY = "clear_chat_history"
    RESET = "reset"
    UPDATE_DATA_SOURCES = "update_data_sources"
    SUMMARY_SPRINT = "summary_sprint"
    GET_JIRA_TICKET_INFO = "get_jira_ticket_info"
    FUNCTION = "function"
    SAVE_FOLDER = "save_folder"
    ADD_CONFLUENCE_PAGE = "add_confluence_page"
    CREATE_NEW_KNOWLEDGE_BASE = "create_new_knowledge_base"
    SUBMIT_JIRA_COMMENT = "submit_jira_comment"
    SUBMIT_CONFLUENCE_COMMENT = "submit_confluence_comment"
    MANAGE_COLLECTIONS = "manage_collections"
    MANAGE_PAGES = "manage_pages"
    MANAGE_JIRA = "manage_jira"
    SHOW_COLLECTION = "show_document"
    SELECT_SOURCE = "select_source"
    REMOVE_COLLECTION = "remove_document"


class RegexActions:
    """Regex actions for adaptive card."""

    SHOW_PAGE: ClassVar[list[str]] = [
        "show_page_source_selected",
        "apply_search",
        "clear_search",
        "show_page_prev_page",
        "show_page_next_page",
    ]

    REMOVE_PAGE: ClassVar[list[str]] = [
        "remove_page_source_selected",
        "remove_apply_search",
        "remove_clear_search",
        "remove_page_prev_page",
        "remove_page_next_page",
        "remove_page_delete_request",
        "remove_page_confirm_delete",
        "remove_entire_source",
        "remove_entire_source_confirm",
        "remove_selected_sources",
        "remove_multiple_sources_confirm",
        "remove_selected_pages",
        "remove_selected_pages_confirm",
    ]

    BOARD: ClassVar[list[str]] = [
        "list_boards",
        "list_boards_prev_page",
        "list_boards_next_page",
        "list_boards_last_page",
        "clear_board_search",
        "search_boards",
    ]

    PROJECT: ClassVar[list[str]] = [
        "list_projects",
        "search_projects",
        "clear_project_search",
        "list_projects_prev_page",
        "list_projects_next_page",
        "list_projects_last_page",
    ]

    COLLECTION: ClassVar[list[str]] = [
        "create_collection_submit",
    ]
    SPRINT: ClassVar[list[str]] = [
        "list_sprints",
        "list_sprints_prev_page",
        "list_sprints_next_page",
        "list_sprints_last_page",
    ]
    TICKET: ClassVar[list[str]] = [
        "list_tickets",
        "list_tickets_prev_page",
        "list_tickets_next_page",
        "list_tickets_last_page",
    ]
    DOCUMENT_SPRINT: ClassVar[list[str]] = [
        "create_document_sprint",
        "submit_sprint_data",
        "update_sprint_list",
    ]


class JiraActions:
    """Jira actions for adaptive card."""

    LIST_PROJECTS = "list_projects"
    LIST_SPRINTS = "list_sprints"
    LIST_TICKETS = "list_tickets"
    STATE_PROJECT = "project_list_activity_id"
    STATE_SPRINT = "sprint_list_activity_id"
    STATE_TICKET = "ticket_list_activity_id"
    LIST_BOARDS = "list_boards"
    STATE_BOARD = "board_list_activity_id"
