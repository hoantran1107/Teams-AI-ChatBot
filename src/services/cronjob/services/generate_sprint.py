import logging
import uuid
from datetime import UTC, datetime

import aiohttp
import markdown
from bs4 import BeautifulSoup

from src.config.settings import (
    atlassian_api_token,
    atlassian_confluence_url,
    atlassian_user,
    enable_generate_sprint_for_ifdcpb,
)
from src.constants.app_constants import MIME_TYPE
from src.services.custom_llm.services.llm_utils import LLMUtils
from src.services.jira_services.services.get_data import (
    get_all_board,
    get_all_field,
    get_all_sprint_in_board,
    get_issues_in_sprint_in_board_async,
)

_logger = logging.getLogger(__name__)
HTML_PARSER = "html.parser"
UTC_OFFSET = "+00:00"


async def generate_sprint(single_board_id: int, project_key: str, bypass: bool) -> None:
    if enable_generate_sprint_for_ifdcpb:
        board = await get_all_board()
        for board_id, board_info in board.items():
            await process_sprints(board_id, board_info["project_key"], bypass)
    else:
        await process_sprints(single_board_id, project_key, bypass)


async def process_sprints(board_id: int, project_key: str, bypass: bool) -> None:
    """Generate document sprint and Upload Confluence Page when sprint end."""
    today = datetime.now(UTC).date()
    sprints = await get_all_sprint_in_board(board_id)
    if not sprints:
        return
    sprint_id, sprint_info = list(sprints.items())[-1]
    end_date = datetime.fromisoformat(
        sprint_info["end_date"].replace("Z", UTC_OFFSET),
    ).date()

    if end_date == today or bypass:
        all_issue_fields = await get_all_field()
        tickets = await get_issues_in_sprint_in_board_async(board_id, sprint_id, all_issue_fields)
        if not tickets:
            return
        response, tickets_id = await generate_context(sprint_info, tickets)
        context = response.content
        await update_confluence(project_key, tickets_id, context)


def jira_ticket_card_macro(issue_key: str, server_id: str | None = None) -> str:
    """Return an <li> containing a Jira Issue card for Confluence Cloud.
    Provide server_id (UUID) only when more than one Jira link exists.
    """
    macro_uuid = uuid.uuid4()  # keeps each macro unique
    parts = [
        f'<ac:structured-macro ac:name="jira" ac:schema-version="1" ac:macro-id="{macro_uuid}">',
        f'  <ac:parameter ac:name="key">{issue_key}</ac:parameter>',
    ]
    if server_id:  # optional
        parts.append(f'  <ac:parameter ac:name="serverId">{server_id}</ac:parameter>')
    # customise displayed columns if you want
    parts.append('  <ac:parameter ac:name="columns">key,summary,status</ac:parameter>')
    parts.append("</ac:structured-macro>")
    return f"<li>{''.join(parts)}</li>"


JIRA_SERVER_ID = None  # Set this to your Jira server ID if interacting with multiple Jira server instances


async def update_confluence(project_key: str, tickets_id: list, context, page_id: int = 3475243531) -> tuple:
    """Upload document sprint to Confluence Sprint."""
    async with aiohttp.ClientSession(
        auth=aiohttp.BasicAuth(atlassian_user, atlassian_api_token),
    ) as session:
        page_data = await fetch_page_data(session, page_id)
        if not page_data:
            return False, f"Not found Confluence Page with {page_id}"

        current_content = page_data["body"]["storage"]["value"]

        html_context = markdown.markdown(context)
        html_ticket_list = generate_ticket_list(tickets_id)

        name_row = ["Project", "Document", "Tickets"]
        new_row = create_new_row(project_key, html_context, html_ticket_list)

        soup = BeautifulSoup(current_content, HTML_PARSER)
        updated = update_existing_table(soup, name_row, new_row)

        if not updated:
            new_table = create_new_table(name_row, new_row)
            soup.append(BeautifulSoup(new_table, HTML_PARSER))

        updated_content = str(soup)
        return await update_page_content(session, page_id, page_data, updated_content)


async def fetch_page_data(session, page_id: int):
    response = await session.get(
        f"{atlassian_confluence_url}/rest/api/content/{page_id}?expand=body.storage,version",
    )
    if response.status != 200:
        return None
    return await response.json()


def generate_ticket_list(tickets_id: list) -> str:
    """Gererate List card tickets."""
    return "<ol>" + "".join(jira_ticket_card_macro(tid.split(":")[0], JIRA_SERVER_ID) for tid in tickets_id) + "</ol>"


def create_new_row(project_key: str, html_context: str, html_ticket_list: str) -> str:
    """Create a new row with the given content."""
    return f"""
    <tr>
        <td>{project_key}</td>
        <td>{html_context}</td>
        <td>{html_ticket_list}</td>
    </tr>
    """


def update_existing_table(soup, name_row: list, new_row: str) -> bool:
    """Add content to the table that matches name_row."""
    for table in soup.find_all("table"):
        for section in (table.find("thead"), table.find("tbody")):
            if not section:
                continue
            if match_table_header(section, name_row):
                tbody = table.find("tbody") or soup.new_tag("tbody")
                table.append(tbody)
                new_tr = BeautifulSoup(new_row, HTML_PARSER)
                tbody.append(new_tr)
                return True
    return False


def match_table_header(section, name_row: list) -> bool:
    """Check table match with name_row."""
    rows = section.find_all("tr", recursive=True)
    for row in rows:
        ths = row.find_all("th", recursive=True)
        if len(ths) == len(name_row):
            th_texts = [th.get_text(strip=True).lower() for th in ths]
            return all(name.lower() in th_texts for name in name_row)
    return False


def create_new_table(name_row: list, new_row: str) -> str:
    """Create a new table with column name_row and table content as new_row."""
    return f"""
    <table style="width: 100%; border-collapse: collapse; table-layout: fixed; margin: 0 auto;">
        <thead>
            <tr>
                {" ".join(f"<th>{header}</th>" for header in name_row)}
            </tr>
        </thead>
        <tbody>
            {new_row}
        </tbody>
    </table>
    """


async def update_page_content(session, page_id: int, page_data, updated_content) -> tuple:
    """Update content to Confluence Page."""
    update_data = {
        "version": {"number": page_data["version"]["number"] + 1},
        "title": page_data["title"],
        "type": "page",
        "body": {"storage": {"value": updated_content, "representation": "storage"}},
    }
    async with session.put(
        f"{atlassian_confluence_url}/rest/api/content/{page_id}",
        json=update_data,
        headers={"Content-Type": MIME_TYPE},
    ) as update_response:
        if update_response.status != 200:
            return False, f"Failed to Upload Confluence Page with {page_id}"
        _logger.info(
            f"Added document to Confluence success. Status: {update_response.status}",
        )
        url = f"{atlassian_confluence_url}/spaces/ifd/pages/{page_id}"
        return True, url


async def generate_context(sprint_info: dict, tickets: dict) -> tuple:
    """Generate document sprint and list tickets in sprint."""
    sprint_name = sprint_info["name"]
    sprint_goal = sprint_info["goal"]
    start_date = datetime.fromisoformat(
        sprint_info["start_date"].replace("Z", UTC_OFFSET),
    ).date()
    end_date = datetime.fromisoformat(
        sprint_info["end_date"].replace("Z", UTC_OFFSET),
    ).date()

    issue_lines = []
    total_story_points = 0
    tickets_id = []

    for key, data in tickets.items():
        story_point = data.get("Story Points", 0) or 0
        issue_type = data.get("Issue Type") or ""
        if issue_type.lower() != "sub-task":
            total_story_points += story_point
        issue_lines.append(
            f"- **{key}**: {data.get('Summary', '')}\n"
            f"  - Description: {data.get('Description', '')}\n"
            f"  - Status: {data.get('Status', '')}\n"
            f"  - Story point: {story_point}",
        )
        tickets_id.append(f"{key}")

    issue_text = "\n".join(issue_lines)

    sprint_header = f"Sprint Name: {sprint_name}\n"
    if sprint_goal:
        sprint_header += f"Goal:\n{sprint_goal}\n"

    num_issues = len(issue_lines)

    sprint_header += f"Start: {start_date}, end: {end_date}\n"
    sprint_header += f"Total tickets: {num_issues}, Total story points: {total_story_points}\n"

    response = f"""
    {sprint_header}
    Issues:
    {issue_text}
    """
    prompt = f"""
    You are given the details of a sprint, including its name, goal, date range, and a list of tickets with their summaries and descriptions.

    Sprint content:
    {response}

    Your task is to generate a **well-structured and readable Markdown document** suitable for sprint review or Confluence reporting.

    ### Instructions:

    1. Start with a summary section:

    - **Sprint Name**: {sprint_name}
    - **Goal**: {sprint_goal}
    If the goal is not provided, analyze the sprint content and propose a suitable goal.
    - **Start**: {start_date}  **- End**: {end_date}.
    - **Total Tickets**: {num_issues} **- Total Story Points**: {total_story_points}.

    2. Analyze the list of tickets and group them into 2–4 logical **Content** (e.g., Backend module Improvements, new UI, Infrastructure...).

    3. For each theme:
    - Use a level-3 heading: themes name
    - Write a 1–2 sentence summary of key work in this theme.
    - **Avoid** generic introductions like "This theme focuses on...". Instead, directly state what was done.
    - Then use:
    - **Accomplishments:** bullet list of tangible outcomes or improvements (e.g., automation, UX, performance gains).
        - For each accomplishment bullet point, if it relates to a specific ticket, add a hyperlink to the ticket at the end of the bullet point using this format: [TICKET-ID](https://infodation.atlassian.net/browse/TICKET-ID)
        - Example: "Enabled bot to store RAG-based chat history with detailed metadata for monitoring, auditing, and analytics. [IFDCPB-313](https://infodation.atlassian.net/browse/IFDCPB-313)"
        - Try to match as many bullet points as possible with their corresponding tickets based on the content.


    4. Keep the writing:
    - Concise and professional
    - Easy to scan using bullet points
    - Suitable for reports or documentation
    - Don't cover by ```markdown```

    5. Do **not** list every ticket individually unless requested.

    6. Optionally end with a short conclusion (e.g., what this sprint enables for the next phase).
    """

    llm = LLMUtils.get_azure_openai_llm()
    response = await llm.ainvoke(prompt)
    return response, tickets_id
