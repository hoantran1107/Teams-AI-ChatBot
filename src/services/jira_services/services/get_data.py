import logging

from src.services.jira_services.services.jira_services import AsyncJira

logger = logging.getLogger(__name__)

# Initialize Jira object
jira = AsyncJira()


async def get_all_board_from_project(project_id: str) -> list:
    """Get all sprints for a project using pagination."""
    try:
        data = await jira.get_all_board_from_project_async(project_id)
        if not data:
            return []
        return data
    except Exception as e:
        logger.error("Error fetching sprints for project %s: %s", project_id, e)
        return []


async def get_all_board() -> dict:
    """Get all Jira boards with pagination or fallback to projects if boards API fails.

    Returns:
        Dictionary mapping board IDs to board data.

    """
    start_at = 0
    max_result = 50  # Jira API limit for boards
    try:
        data = await jira.get_all_agile_boards(start=start_at, limit=max_result)
        if data and data.get("total", 0) > 0:
            return await _fetch_boards_with_pagination(data["total"], max_result, data)
        return await fetch_fallback_projects()
    except Exception as e:
        logger.error("Error fetching boards: %s", e)
        return await fetch_fallback_projects()


async def _fetch_boards_with_pagination(total: int, max_result: int, initial_data: dict) -> dict:
    """Fetch all boards using pagination.

    Args:
        total: Total number of boards.
        max_result: Maximum number of results per page.
        initial_data: Initial data from first API call.

    Returns:
        Dictionary mapping board IDs to board data.

    """
    boards_dict = {}
    pages = (total + max_result - 1) // max_result

    for page in range(pages):
        start_at = page * max_result
        page_data = initial_data if page == 0 else await jira.get_all_agile_boards(start=start_at, limit=max_result)
        if not page_data or not page_data.get("values"):
            break
        for item in page_data["values"]:
            board_id, board_data = _process_board_item(item)
            if board_id and board_data:
                boards_dict[board_id] = board_data
    return boards_dict


def _process_board_item(item: dict) -> list:
    """Process a single board item.

    Args:
        item: Dictionary containing board data.

    Returns:
        Tuple of board ID and processed board data.

    """
    board_id = item.get("id")
    board_type = item.get("type") or ""
    if board_type != "scrum":
        return [None, None]
    loc = item.get("location") or {}
    board_data = {
        "name": item.get("name") or "",
        "project_id": loc.get("projectId") or "",
        "display_name": loc.get("displayName") or "",
        "project_name": loc.get("projectName") or "",
        "project_key": loc.get("projectKey") or "",
        "location_name": loc.get("name") or "",
    }
    return [board_id, board_data]


async def fetch_fallback_projects() -> dict:
    """Fetch projects as fallback when boards API fails.

    Returns:
        Dictionary mapping project IDs to project data.

    """
    try:
        projects = await jira.get_jira_projects_async()
        if not projects:
            return {}
        projects_dict = {}
        for project in projects:
            project_id = project.get("id")
            if project.get("projectCategory", {}).get("name") not in ["Inactive", "Closed"]:
                projects_dict[project_id] = {
                    "name": project.get("name") or "",
                    "project_id": project_id,
                    "project_key": project.get("key") or "",
                }

        return projects_dict
    except Exception as e:
        logger.error("Error fetching projects: %s", e)
        return {}


async def get_all_sprint_in_board(board_id: int) -> dict:
    """Get all sprints for a board using pagination.

    Args:
        board_id: ID of the board.

    Returns:
        Dictionary mapping sprint IDs to sprint data.

    """
    start_at = 0
    max_result = 50  # Jira API limit for sprints
    try:
        data = await jira.get_all_sprints_from_board(board_id, start=start_at, limit=max_result)
        if not data:
            return {}
        return await _fetch_sprints_with_pagination(board_id, data["total"], max_result, data)
    except Exception as e:
        logger.error("Error fetching sprints for board %s: %s", board_id, e)
        return {}


async def _fetch_sprints_with_pagination(
    board_id: int,
    total: int,
    max_result: int,
    initial_data: dict,
) -> dict:
    """Fetch all sprints using pagination.

    Args:
        board_id: ID of the board.
        total: Total number of sprints.
        max_result: Maximum number of results per page.
        initial_data: Initial data from first API call.

    Returns:
        Dictionary mapping sprint IDs to sprint data.

    """
    sprints_dict = {}
    pages = (total + max_result - 1) // max_result
    for page in range(pages):
        page_data = (
            initial_data
            if page == 0
            else await jira.get_all_sprints_from_board(board_id=board_id, start=page * max_result, limit=max_result)
        )
        if not page_data or not page_data.get("values"):
            break
        for item in page_data["values"]:
            sprint_id, sprint_data = _process_sprint_item(item)
            if sprint_id and sprint_data:
                sprints_dict[sprint_id] = sprint_data
    return sprints_dict


def _process_sprint_item(item: dict) -> list:
    sprint_id = item.get("id")
    if sprint_id:
        sprint_data = {
            "name": item.get("name") or "",
            "origin_board_id": item.get("originBoardId") or "",
            "state": item.get("state") or "",
            "goal": item.get("goal") or "",
            "start_date": item.get("startDate") or "",
            "end_date": item.get("endDate") or "",
            "complete_date": item.get("completeDate") or "",
        }
        return [sprint_id, sprint_data]
    return [None, None]


async def get_issues_in_sprint_in_board_async(board_id: int, sprint_id: int, all_issue_fields: dict) -> dict:
    """Get all issues for a sprint in a board using pagination.

    Args:
        board_id: ID of the board.
        sprint_id: ID of the sprint.
        all_issue_fields: Dictionary mapping field indices to field data.

    Returns:
        Dictionary mapping issue keys to issue data.

    """
    start_at = 0
    max_result = 1000  # Jira API limit for issues

    try:
        data = await jira.get_all_issues_for_sprint_in_board(
            board_id,
            sprint_id,
            start=start_at,
            limit=max_result,
        )
        if not data or data.get("total", 0) == 0:
            return {}
        return await _fetch_issues_with_pagination(board_id, sprint_id, max_result, data, all_issue_fields)
    except Exception as e:
        logger.error("Error fetching issues for board %s, sprint %s: %s", board_id, sprint_id, e)
        return {}


async def _fetch_issues_with_pagination(
    board_id: int,
    sprint_id: int,
    max_result: int,
    initial_data: dict,
    all_issue_fields: dict,
) -> dict:
    """Fetch all issues using pagination.

    Args:
        board_id: ID of the board.
        sprint_id: ID of the sprint.
        max_result: Maximum number of results per page.
        initial_data: Initial data from first API call.
        all_issue_fields: Dictionary mapping field indices to field data.

    Returns:
        Dictionary mapping issue keys to issue data.

    """
    issues_dict = {}
    total = initial_data.get("total") or 0
    pages = (total + max_result - 1) // max_result
    for page in range(pages):
        page_data = (
            initial_data
            if page == 0
            else await jira.get_all_issues_for_sprint_in_board(
                board_id=board_id,
                sprint_id=sprint_id,
                start=page * max_result,
                limit=max_result,
            )
        )
        if not page_data or not page_data.get("issues"):
            break
        for item in page_data["issues"]:
            issue_key = item.get("key") or ""
            issue_data = _get_issue_data(item, all_issue_fields)
            if issue_key and issue_data:
                issues_dict[issue_key] = issue_data
    return issues_dict


async def get_content_jira(ticket_key: str, all_issue_fields: dict) -> dict:
    """Get content for a specific Jira ticket.

    Args:
        ticket_key: The key of the ticket (e.g., DEMO-123).
        all_issue_fields: Dictionary mapping field indices to field data.

    Returns:
        Dictionary mapping ticket key to ticket data.

    """
    try:
        data = await jira.issue(key=ticket_key)
        if not data:
            return {}

        issue_data = _get_issue_data(data, all_issue_fields)
        return {ticket_key: issue_data}
    except Exception as e:
        logger.error("Error fetching ticket %s: %s", ticket_key, e)
        return {}


async def add_comment_to_ticket(ticket_key: str, comment_body: str) -> dict:
    """Add a comment to a Jira ticket.

    Args:
        ticket_key (str): The Jira ticket key (e.g., "IFDCPB-123").
        comment_body (str): The comment text to add.

    Returns:
        dict: Response from the API containing the created comment or error information.

    """
    try:
        result = await jira.add_comment(ticket_key, comment_body)
        if result:
            return {
                "success": True,
                "message": f"Comment added successfully to {ticket_key}",
                "comment_id": result.get("id"),
                "created": result.get("created"),
                "author": result.get("author", {}).get("displayName", "Unknown"),
            }
        else:
            return {"success": False, "message": f"Failed to add comment to {ticket_key}. No response from API."}
    except Exception as e:
        logger.error("Error adding comment to ticket '%s': %s", ticket_key, e)
        return {"success": False, "message": f"Error adding comment to {ticket_key}: {str(e)}"}


def extract_text_from_adf(adf: dict) -> str:
    """Convert ADF (Atlassian Document Format) description to plain text.

    Args:
        adf: Dictionary containing ADF content.

    Returns:
        Extracted plain text from ADF.

    """
    result = []

    def recurse(node) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text" and "text" in node:
                result.append(node["text"])
            for value in node.values():
                recurse(value)
        elif isinstance(node, list):
            for item in node:
                recurse(item)

    try:
        recurse(adf)
        return "\n".join(result)
    except Exception as e:
        logger.error("Error extracting ADF text: %s", e)
        return ""


async def get_all_tickets_jql(jql: str, all_issue_fields: dict) -> dict:
    """Get all Jira tickets using JQL with pagination.

    Args:
        jql: JQL query string.
        all_issue_fields: Dictionary mapping field indices to field data.

    Returns:
        Dictionary mapping ticket keys to ticket data.

    """
    start_at = 0
    max_result = 100  # Jira API limit for search

    try:
        data = await jira.jql(jql=jql, start=start_at, limit=max_result)
        if not data or data.get("total", 0) == 0:
            return {}
        return await _fetch_tickets_jql_with_pagination(jql, max_result, data, all_issue_fields)
    except Exception as e:
        logger.error("Error fetching tickets for JQL '%s': %s", jql, e)
        return {}


async def _fetch_tickets_jql_with_pagination(
    jql: str,
    max_result: int,
    initial_data: dict,
    all_issue_fields: dict,
) -> dict:
    """Fetch all tickets using JQL with pagination.

    Args:
        jql: JQL query string.
        max_result: Maximum number of results per page.
        initial_data: Initial data from first API call.
        all_issue_fields: Dictionary mapping field indices to field data.

    Returns:
        Dictionary mapping ticket keys to ticket data.

    """
    ticket_dict = {}
    total = initial_data.get("total", 0)
    pages = (total + max_result - 1) // max_result
    for page in range(pages):
        page_data = initial_data if page == 0 else await jira.jql(jql=jql, start=page * max_result, limit=max_result)
        if not page_data or not page_data.get("issues"):
            break
        for item in page_data["issues"]:
            issue_key = item.get("key") or ""
            issue_data = _get_issue_data(item, all_issue_fields)
            if issue_key and issue_data:
                ticket_dict[issue_key] = issue_data
    return ticket_dict


async def get_all_field() -> dict:
    """Get all Jira fields with their id, names and clause names.

    Returns:
        Dictionary mapping field indices to field data.

    """
    try:
        data = await jira.get_all_fields()
        if not data:
            return {}
        field_dict = {}
        for field in data:
            clause_names = field.get("clauseNames", [])
            field_id = field.get("id") or None
            if clause_names and field_id:
                field_dict[field_id] = {
                    "name": field.get("name") or "",
                    "clause_names": clause_names[0] if clause_names else "",
                }
        return field_dict
    except Exception as e:
        logger.error("Error fetching fields: %s", e)
        return {}


async def find_account_id(query: str) -> list:
    """Get account ID by user name."""
    try:
        data = await jira.find_account_id(query)
        if not data:
            return []
        # Get the first account ID and display name
        return [data[0].get("accountId"), data[0].get("displayName")]
    except Exception as e:
        logger.error("Error fetching account ID: %s", e)
        return []


def _get_issue_data(item: dict, all_issue_fields: dict) -> dict:
    """Get the issue data from the Jira API.

    Args:
        item: Dictionary containing issue data.
        all_issue_fields: Dictionary mapping field indices to field data.

    Returns:
        Dictionary containing processed issue data.

    """
    fields = item.get("fields") or {}
    issue_data = {}

    for key, value in fields.items():
        # Skip empty values
        if not value:
            continue

        # Normalize value to list, object, string
        extracted = None
        if isinstance(value, list):
            extracted_lines = []
            for v in value:
                data = v.get("value") or v.get("name") or v.get("displayName") or None if isinstance(v, dict) else v
                if data:
                    extracted_lines.append(data)
            extracted = "\n".join(extracted_lines)

        elif isinstance(value, dict):
            extracted = value.get("value") or value.get("name") or value.get("displayName") or None
        else:
            extracted = value

        if extracted:
            # Determine display name
            field_info = all_issue_fields.get(key)
            name = field_info.get("name") if field_info else key
            issue_data[name] = extracted
    return issue_data
