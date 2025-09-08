import re

from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.bots.handlers.attachment import handel_upload_files_to_gcp
from src.bots.handlers.commands import handle_command
from src.bots.handlers.data_sources import update_data_sources
from src.bots.handlers.greeting import handle_clear_chat_history, handle_new_chat, handle_reset
from src.bots.handlers.handle_document_sprint import handle_document_sprint
from src.bots.handlers.handler_confluence_comment import (
    handle_cancel_confluence_comment,
    handle_submit_confluence_comment,
)
from src.bots.handlers.handler_jira_comment import handle_cancel_comment, handle_submit_jira_comment
from src.bots.handlers.handler_jira_sprint import handle_summarize_sprint
from src.bots.handlers.handler_jira_ticket import handle_get_jira_ticket_info
from src.bots.handlers.jira_sentiment import handle_draft_submission
from src.bots.handlers.list_project import handle_list_boards, handle_list_projects
from src.bots.handlers.manage_collection import handle_collection_actions, handle_create_collection_request
from src.bots.handlers.modify_collection_pages import handle_add_page_request
from src.bots.handlers.modify_collection_pages_handler import (
    handle_add_page_actions,
    handle_remove_page_actions,
    handle_show_page_actions,
)
from src.constants.action_types import ExactActions, RegexActions


def register_handle_submit_actions(bot_app):
    @bot_app.adaptive_cards.action_submit(ExactActions.SUBMIT_DRAFT)
    async def _(context: TurnContext, state: AppTurnState):
        return await handle_draft_submission(context, state)

    @bot_app.adaptive_cards.action_submit(re.compile(f"^({'|'.join(RegexActions.SHOW_PAGE)})$"))
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_show_page_actions(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.ADD_PAGE_SUBMIT)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_add_page_actions(context, state)

    @bot_app.adaptive_cards.action_submit(re.compile(f"^({'|'.join(RegexActions.REMOVE_PAGE)})$"))
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_remove_page_actions(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.UPDATE_DATA_SOURCES)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await update_data_sources(context, state)

    @bot_app.adaptive_cards.action_submit(re.compile(f"^({'|'.join(RegexActions.PROJECT)})$"))
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_list_projects(context, state)

    @bot_app.adaptive_cards.action_submit(re.compile(f"^({'|'.join(RegexActions.BOARD)})$"))
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_list_boards(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.NEW_CHAT)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_new_chat(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.CLEAR_CHAT_HISTORY)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_clear_chat_history(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.RESET)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_reset(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.SUMMARY_SPRINT)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_summarize_sprint(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.GET_JIRA_TICKET_INFO)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_get_jira_ticket_info(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.FUNCTION)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_command(context, state)

    @bot_app.adaptive_cards.action_submit(re.compile(f"^({'|'.join(RegexActions.COLLECTION)})$"))
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_collection_actions(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.SAVE_FOLDER)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handel_upload_files_to_gcp(context, state)

    @bot_app.adaptive_cards.action_submit(re.compile(f"^({'|'.join(RegexActions.DOCUMENT_SPRINT)})$"))
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_document_sprint(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.CREATE_NEW_KNOWLEDGE_BASE)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_create_collection_request(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.ADD_CONFLUENCE_PAGE)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_add_page_request(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.SUBMIT_JIRA_COMMENT)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_submit_jira_comment(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.SUBMIT_CONFLUENCE_COMMENT)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_submit_confluence_comment(context, state)

    @bot_app.adaptive_cards.action_submit(ExactActions.CANCEL_COMMENT)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_cancel_comment(context)

    @bot_app.adaptive_cards.action_submit(ExactActions.CANCEL_CONFLUENCE_COMMENT)
    async def _(context: TurnContext, state: AppTurnState, action: str):
        return await handle_cancel_confluence_comment(context)
