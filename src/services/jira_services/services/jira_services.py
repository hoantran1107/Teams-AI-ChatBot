from typing import Any

from aiohttp import BasicAuth

from src.config.settings import atlassian_api_token, atlassian_jira_url, atlassian_user
from src.constants.app_constants import MIME_TYPE
from src.services.jira_services.services.client_session import ClientSession


class AsyncJira:
    """Asynchronous Jira API client using aiohttp."""

    def __init__(
        self,
        base_url: str = atlassian_jira_url,
        username: str = atlassian_user,
        api_token: str = atlassian_api_token,
    ) -> None:
        """Initialize the Jira API client.

        Args:
            base_url (str): The base URL of the Jira instance.
            username (str): Jira username (email).
            api_token (str): API token for authentication.

        """
        self.base_url = base_url.rstrip("/")
        self.auth = BasicAuth(username, api_token)
        self.headers = {
            "Accept": MIME_TYPE,
            "Content-Type": "application/json",
        }

    async def _request(self, endpoint: str, params: dict | None = None) -> Any | None:
        """Make a GET request to the Jira API.

        Args:
            endpoint (str): The API endpoint path.
            params (dict, optional): Query parameters.

        Returns:
            dict | None: JSON response from the API.

        """
        url = f"{self.base_url}{endpoint}"
        async with ClientSession(headers=self.headers, auth=self.auth) as session:
            return await session.get_json(url, params=params)

    async def _post_request(self, endpoint: str, data: dict) -> dict | None:
        """Make a POST request to the Jira API.

        Args:
            endpoint (str): The API endpoint path.
            data (dict): Data to send in the request body.

        Returns:
            dict | None: JSON response from the API.

        """
        url = f"{self.base_url}{endpoint}"
        async with ClientSession(headers=self.headers, auth=self.auth) as session:
            return await session.post_json(url, data=data)

    async def get_all_agile_boards(self, start: int = 0, limit: int = 50) -> dict | None:
        """Get all Jira agile boards."""
        params = {"startAt": start, "maxResults": limit}
        return await self._request("/rest/agile/1.0/board", params)

    async def get_all_sprints_from_board(
        self,
        board_id: int,
        start: int = 0,
        limit: int = 50,
    ) -> dict | None:
        """Get all sprints for a given board."""
        params = {"startAt": start, "maxResults": limit}
        return await self._request(f"/rest/agile/1.0/board/{board_id}/sprint", params)

    async def get_all_issues_for_sprint_in_board(
        self,
        board_id: int,
        sprint_id: int,
        start: int = 0,
        limit: int = 1000,
        fields: list | None = None,
    ) -> dict | None:
        """Get all issues for a sprint in a given board."""
        params = {"startAt": start, "maxResults": limit}
        if fields:
            params["fields"] = ",".join(fields)
        return await self._request(f"/rest/agile/1.0/board/{board_id}/sprint/{sprint_id}/issue", params)

    async def jql(
        self,
        jql: str,
        start: int = 0,
        limit: int = 100,
        fields: list | None = None,
    ) -> dict | None:
        """Run a JQL query to search for issues."""
        params = {"jql": jql, "startAt": start, "maxResults": limit}
        if fields:
            params["fields"] = ",".join(fields)
        return await self._request("/rest/api/2/search", params)

    async def issue(self, key: str, fields: list | None = None) -> dict | None:
        """Get details of an issue by its key."""
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        return await self._request(f"/rest/api/2/issue/{key}", params)


    async def add_comment(self, issue_key: str, comment_body: str) -> dict | None:
        """Add a comment to a Jira issue.

        Args:
            issue_key (str): The Jira issue key (e.g., "IFDCPB-123").
            comment_body (str): The comment text to add.

        Returns:
            dict | None: JSON response from the API containing the created comment.

        """
        data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": comment_body
                            }
                        ]
                    }
                ]
            }
        }
        return await self._post_request(f"/rest/api/3/issue/{issue_key}/comment", data)

    async def get_jira_projects_async(self) -> dict | None:
        """Get all Jira projects."""
        return await self._request("/rest/api/3/project")

    async def find_account_id(self, query: str) -> dict | None:
        """Find account ID by query."""
        params = {"query": query}
        return await self._request("/rest/api/3/user/search", params)

    async def get_all_fields(self) -> dict | None:
        """Retrieve all Jira fields."""
        return await self._request("/rest/api/3/field")

    async def get_all_board_from_project_async(
        self,
        project_key_or_id: str,
        start: int = 0,
        limit: int = 50,
    ) -> list:
        """Get all sprints for a project using pagination."""
        all_board = []
        current_start = start
        while True:
            params = {"startAt": current_start, "maxResults": limit, "projectKeyOrId": project_key_or_id}
            response = await self._request("/rest/agile/1.0/board", params)
            if response is None:
                return []
            all_board.extend([board for board in response.get("values", []) if board.get("type") == "scrum"])
            if not response.get("isLast", False):
                current_start += limit
            else:
                break
        return all_board
