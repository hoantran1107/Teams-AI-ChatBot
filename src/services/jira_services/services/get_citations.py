from src.config.settings import atlassian_jira_url


def get_jiraticket_citations(ticket_ids: list) -> list:
    """Add formatted citations to the response."""
    if not ticket_ids:
        return []
    citations = []
    for i, ticket_id in enumerate(ticket_ids, start=1):
        citations.append({"position": i, "url": f"{atlassian_jira_url}/browse/{ticket_id.strip()}"})
    return citations


def get_jira_sprint_citations(board_id: int, sprint_id: int, project_key: str, sprint_state: str) -> str:
    """Get citations for the sprint."""
    if sprint_state == "closed":
        url = f"{atlassian_jira_url}/jira/software/c/projects/{project_key}/boards/{board_id}/reports/sprint-retrospective?sprint={sprint_id}"
    else:
        url = f"{atlassian_jira_url}/jira/software/c/projects/{project_key}/boards/{board_id}/backlog"

    return url
