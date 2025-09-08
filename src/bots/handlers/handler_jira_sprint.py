import logging

from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.services.jira_services.services.get_citations import get_jira_sprint_citations
from src.services.jira_services.services.get_data import (
    get_all_board,
    get_all_field,
    get_all_sprint_in_board,
    get_issues_in_sprint_in_board_async,
)
from src.services.jira_services.services.jira_utils import (
    extract_context_data,
    find_board_id,
    find_sprint_id,
    send_response,
)

_logger = logging.getLogger(__name__)


async def handle_summarize_sprint(context: TurnContext, state: AppTurnState) -> str | None:
    """Summary Sprint."""
    sprint_context = await _get_sprint_info(context)
    if not isinstance(sprint_context, list):
        _logger.error("No sprint information found.")
        return "No sprint information found."

    issue_text, board_name, sprint_data, citations = sprint_context
    sprint_name = sprint_data.get("name", "")

    prompt_text = f"""
    You are given the details of a sprint, including its name, goal (if available), and a list of ticket summaries and descriptions.

    ### 📥 Sprint Content
    **Sprint_data**: {sprint_data}
    **Issues of Sprint**: {issue_text}
    **References**:{citations}

    ### 🧭 Task
    Write a structured sprint summary in professional report style. If the sprint goal is not explicitly stated, infer the main intent from the ticket content.

    ### ✅ Guidelines:
    - Start with a **Sprint Goal**: 1–2 concise sentences that summarize the key objective of this sprint.
    - Then write a **What was achieved** section:
    - Identify 3–5 meaningful themes based on the ticket content (e.g., User Interaction, Automation, Knowledge Base Management)
    - Under each theme, write 1–3 bullet points (max 15 words per bullet) describing major accomplishments
    - Use action verbs like *Developed, Improved, Enabled, Automated, Created, Integrated...*

    ### ✍️ Output Format:
    - Markdown
    - Start with:
    **Sprint**: **{sprint_name}**
    **Sprint Summary: {sprint_name}**

    **Sprint Goal**
    [Short paragraph summarizing the goal]

    **What was achieved**
    - **[Theme Name]**
    + [Bullet point 1]
    + [Bullet point 2]

    - **[Another Theme Name]**
    + [Bullet point 1]

    ...

    - Do not include reference numbers (e.g., [¹], [²]) in the main content (e.g., Description, Summary).
    - If citations are provided, include a **References** section at the end of the document.
    - Format the **References** section as a single line: `**References** [¹](url1) [²](url2) ...`, where each `[¹]`, `[²]`, etc., is a clickable hyperlink to the corresponding citation URL.
    - Citations are provided as a list of dictionaries, each with `position` (a number) and `url` (a string). Process this list to create the Markdown format, sorted by `position`.
    - If no citations are provided or the list is empty, omit the **References** section.

    ### 📌 Notes:
    - Do not copy from the ticket descriptions.
    - Make the summary clean, concise (200–300 words), and suitable for sharing with stakeholders or adding to a sprint report.
    - Ensure citations are clearly listed, numbered, and linked correctly to their corresponding numbered squares in the summary.
    - The number of citation markers ([¹], [²], etc.) must equal the number of citations provided in the input.
    - Do not wrap the entire output in ```markdown``` blocks.
    """

    user_content = f"Summary Sprint {sprint_name} of board {board_name}"
    return await send_response(context, state, prompt_text, user_content)


async def _get_sprint_info(context: TurnContext) -> str | list:
    """Get Jira sprint information."""
    # Get data from Adaptive card action
    if not context.activity.value:
        # Get data from user input
        sprint_context = await get_data(context)
        if not isinstance(sprint_context, list):
            return sprint_context
    else:
        # Get data from Adaptive card action
        sprint_context = get_action_data(context)

    board_id, board_name, project_key, sprint_id, sprint_data = sprint_context

    sprint_name = sprint_data.get("name", "")
    sprint_state = sprint_data.get("state", "")

    all_issue_fields = await get_all_field()
    issues = await get_issues_in_sprint_in_board_async(board_id, sprint_id, all_issue_fields)
    if not issues:
        return f"No issues found in sprint '{sprint_name}' of board '{board_name}'."

    issue_text = _get_issue_text(issues)
    citations = get_jira_sprint_citations(board_id, sprint_id, project_key, sprint_state)

    return [issue_text, board_name, sprint_data, citations]


def _validate_input(board_name: str, sprint_name: str) -> tuple[bool, str]:
    """Validate that required parameters are provided."""
    if not board_name or not sprint_name:
        missing_fields = []
        if not board_name:
            missing_fields.append("board name")
        if not sprint_name:
            missing_fields.append("sprint name")
        error_msg = f"❌ **Missing Required Fields**: Please provide {' and '.join(missing_fields)}."
        return False, error_msg
    return True, ""


def _get_issue_text(issues: dict) -> str:
    """Generate text representation of issues."""
    issue_lines = [
        f"- **{key}**: {data.get('Summary') or ''}\n  - Description: {data.get('Description') or ''}\n"
        for key, data in issues.items()
    ]
    return "\n".join(issue_lines)


def get_action_data(context: TurnContext) -> tuple:
    """Get data from Adaptive card action."""
    return extract_context_data(
        context,
        ["board_id", "board_name", "project_key", "sprint_id", "sprint_data"],
    )


async def get_data(context: TurnContext) -> str | list:
    """Get data from user input."""
    # Extract input data
    sprint_name, board_name = extract_context_data(context, ["sprint_name", "board_name"])

    # Validate input
    valid, error_msg = _validate_input(board_name, sprint_name)
    if not valid:
        return error_msg

    # Get all boards
    boards = await get_all_board()
    board_id, board_data = find_board_id(boards, board_name)
    if not board_id or not board_data:
        return f"No board found with name: {board_name} or board has no sprints.\nPlease provide board name"

    project_key = board_data.get("project_key") or ""

    # Get all sprints
    sprints = await get_all_sprint_in_board(board_id)
    sprint_id, sprint = find_sprint_id(sprints, sprint_name)
    if not sprint_id or not sprint:
        return (
            f"No sprint named '{sprint_name}' found in board '{board_name}'.Please provide sprint name and board name"
        )
    return [board_id, board_name, project_key, sprint_id, sprint]
