from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.bots.data_model.history_adaptive_card import save_history
from src.services.custom_llm.services.llm_utils import LLMUtils


def extract_context_data(context: TurnContext, keys: list) -> tuple:
    """Extract multiple keys from context.activity.value or context.data."""
    if context.activity.value:
        return tuple(context.activity.value.get(key) for key in keys)

    data = getattr(context, "data", {}) or {}
    return tuple(data.get(key) for key in keys)


def find_board_id(boards: dict, board_name: str) -> list:
    """Find board ID by matching board name against multiple fields."""
    for bid, data in boards.items():
        info = data or {}
        possible_names = {
            (info.get("name") or "").lower(),
            (info.get("display_name") or "").lower(),
            (info.get("project_name") or "").lower(),
            (info.get("project_key") or "").lower(),
            (info.get("location_name") or "").lower(),
        }
        if board_name.lower() in possible_names:
            return [bid, info]
    return [None, None]


def find_sprint_id(sprints: dict, sprint_name: str) -> list:
    """Find sprint ID by matching sprint name."""
    sprint_name_lower = sprint_name.lower()
    for sid, sprint in sprints.items():
        if sprint.get("name", "").lower() == sprint_name_lower:
            return [sid, sprint]
    return [None, None]


async def send_response(
    context: TurnContext,
    state: AppTurnState,
    prompt_text: str,
    user_content: str,
) -> str | None:
    """Process a prompt with LLM and send the result."""
    try:
        if not context.activity.value:
            return prompt_text

        prompt_output = await process_llm_prompt(prompt_text)
        await context.send_activity(str(prompt_output))
        save_history(state, user_content, prompt_output)
        return None
    except Exception as e:
        return f"**Error**: Failed to format projects: {e!s}"


async def process_llm_prompt(prompt_text: str):
    """Process a prompt with LLM and return the result."""
    llm = LLMUtils.get_azure_openai_llm()
    prompt_content = await llm.ainvoke(prompt_text)
    prompt_output = prompt_content.content
    return prompt_output
