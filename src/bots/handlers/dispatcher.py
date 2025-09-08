import logging
import re

from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.bots.handlers.attachment import handel_upload_files_to_gcp
from src.bots.handlers.commands import handle_command
from src.bots.handlers.data_sources import handle_data_source_selection, update_data_sources
from src.bots.handlers.greeting import (
    handle_clear_chat_history,
    handle_new_chat,
    handle_reset,
)
from src.bots.handlers.handle_document_sprint import handle_document_sprint
from src.bots.handlers.handle_manage_collection import handle_manage_collections
from src.bots.handlers.handle_manage_jira import handle_manage_jira
from src.bots.handlers.handle_manage_page import handle_manage_pages
from src.bots.handlers.handler_confluence_comment import (
    handle_cancel_confluence_comment,
    handle_submit_confluence_comment,
)
from src.bots.handlers.handler_jira_comment import handle_cancel_comment, handle_submit_jira_comment
from src.bots.handlers.handler_jira_sprint import handle_summarize_sprint
from src.bots.handlers.handler_jira_ticket import handle_get_jira_ticket_info
from src.bots.handlers.jira_sentiment import handle_draft_submission
from src.bots.handlers.list_project import handle_list_boards, handle_list_projects
from src.bots.handlers.list_sprint import handle_list_sprints_action
from src.bots.handlers.list_ticket import handle_list_tickets_action
from src.bots.handlers.manage_collection import (
    handle_collection_actions,
    handle_create_collection_request,
)
from src.bots.handlers.modify_collection_pages import (
    handle_add_page_request,
    handle_remove_page_request,
    handle_show_page_request,
)
from src.bots.handlers.modify_collection_pages_handler import (
    handle_add_page_actions,
    handle_remove_page_actions,
    handle_show_page_actions,
)
from src.constants.action_types import ExactActions, RegexActions

action_handlers = {
    ExactActions.SUBMIT_DRAFT: handle_draft_submission,
    ExactActions.ADD_PAGE_SUBMIT: handle_add_page_actions,
    ExactActions.NEW_CHAT: handle_new_chat,
    ExactActions.CLEAR_CHAT_HISTORY: handle_clear_chat_history,
    ExactActions.RESET: handle_reset,
    ExactActions.UPDATE_DATA_SOURCES: update_data_sources,
    ExactActions.SUMMARY_SPRINT: handle_summarize_sprint,
    ExactActions.GET_JIRA_TICKET_INFO: handle_get_jira_ticket_info,
    ExactActions.FUNCTION: handle_command,
    ExactActions.SAVE_FOLDER: handel_upload_files_to_gcp,
    ExactActions.CREATE_NEW_KNOWLEDGE_BASE: handle_create_collection_request,
    ExactActions.ADD_CONFLUENCE_PAGE: handle_add_page_request,
    ExactActions.SUBMIT_JIRA_COMMENT: handle_submit_jira_comment,
    ExactActions.SUBMIT_CONFLUENCE_COMMENT: handle_submit_confluence_comment,
    ExactActions.CANCEL_COMMENT: handle_cancel_comment,
    ExactActions.CANCEL_CONFLUENCE_COMMENT: handle_cancel_confluence_comment,
    ExactActions.MANAGE_PAGES: handle_manage_pages,
    ExactActions.MANAGE_COLLECTIONS: handle_manage_collections,
    ExactActions.MANAGE_JIRA: handle_manage_jira,
    ExactActions.SHOW_COLLECTION: handle_show_page_request,
    ExactActions.SELECT_SOURCE: handle_data_source_selection,
    ExactActions.REMOVE_COLLECTION: handle_remove_page_request,
}

regex_handlers = [
    (re.compile(f"^({'|'.join(RegexActions.SHOW_PAGE)})$"), handle_show_page_actions),
    (re.compile(f"^({'|'.join(RegexActions.REMOVE_PAGE)})$"), handle_remove_page_actions),
    (re.compile(f"^({'|'.join(RegexActions.PROJECT)})$"), handle_list_projects),
    (re.compile(f"^({'|'.join(RegexActions.BOARD)})$"), handle_list_boards),
    (re.compile(f"^({'|'.join(RegexActions.COLLECTION)})$"), handle_collection_actions),
    (re.compile(f"^({'|'.join(RegexActions.SPRINT)})$"), handle_list_sprints_action),
    (re.compile(f"^({'|'.join(RegexActions.TICKET)})$"), handle_list_tickets_action),
    (re.compile(f"^({'|'.join(RegexActions.DOCUMENT_SPRINT)})$"), handle_document_sprint),
]


async def dispatch_submit_action(action: str, context: TurnContext, state: AppTurnState):
    """Dispatch the submit action to the appropriate handler."""
    if action in action_handlers:
        handler = action_handlers[action]
        return await handler(context, state)

    for pattern, handler in regex_handlers:
        if pattern.match(action):
            return await handler(context, state)

    logging.error("No handler found for action: %s", action)
    return None
