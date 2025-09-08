import requests
from datetime import datetime
from typing import Any, Dict
from src.config.settings import atlassian_jira_url
from src.services.jira_sentiment_agentic.services.jira_auth import get_jira_auth
from src.constants.llm_constant import AZURE_LLM00


class JiraService:
    """
    A service class to interact with Jira API for ticket management.

    Attributes:
        base_url: The base URL for the Jira API
        auth: The authentication credentials for Jira API
    """

    def __init__(self):
        self.base_url = atlassian_jira_url
        self.auth = get_jira_auth()

    def get_ticket_details(self, ticket_id: str) -> Dict[str, Any]:
        """
        Get details about a Jira ticket

        Args:
            ticket_id: The Jira ticket ID (e.g., JSM-1234)

        Returns:
            Dictionary containing ticket details

        Raises:
            Exception: If ticket retrieval fails
        """
        auth = get_jira_auth()

        url = f"{atlassian_jira_url}/rest/api/3/issue/{ticket_id}?fields=summary,description,status,reporter,priority,reporter,assignee,status,comment,created,updated"

        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        try:
            response = requests.get(url, headers=headers, auth=auth)
            response.raise_for_status()

            issue_data = response.json()
            description = issue_data["fields"]["description"]

            from langchain_core.prompts import PromptTemplate

            prompt = PromptTemplate(
                input_variables=["description"],
                template="Extract the text from the description field: {description}",
            )
            chain = prompt | AZURE_LLM00
            ai_msg = chain.invoke({"description": description})
            # Build ticket details
            ticket_details = {
                "key": issue_data["key"],  # This works fine as confirmed
                "summary": issue_data["fields"]["summary"],
                "description": ai_msg.content,
                "status": issue_data["fields"]["status"]["name"],
                "created": issue_data["fields"]["created"],
                "updated": issue_data["fields"]["updated"],
                "priority": issue_data["fields"]
                .get("priority", {})
                .get("name", "Not set"),
                "reporter": issue_data["fields"]
                .get("reporter", {})
                .get("displayName", "Unknown"),
                "assignee": issue_data["fields"]
                .get("assignee", {})
                .get("displayName", "Unassigned"),
            }

            formatted_comments = []
            comments = issue_data["fields"].get("comment", {}).get("comments", [])
            for comment in comments:
                created_date = datetime.strptime(
                    comment["created"].split("T")[0], "%Y-%m-%d"
                )
                formatted_date = created_date.strftime("%b %d, %Y")

                formatted_comments.append(
                    {
                        "id": comment["id"],
                        "author": comment["author"]["displayName"],
                        "body": comment["body"],
                        "created": formatted_date,
                        "updated": comment["updated"],
                    }
                )

            ticket_details["comments"] = formatted_comments
            return ticket_details

        except requests.exceptions.RequestException as e:
            error_msg = f"Error retrieving ticket details: {str(e)}"
            if hasattr(e, "response") and e.response is not None:
                error_msg += f" - Status code: {e.response.status_code}"
                if e.response.status_code == 404:
                    error_msg = f"Ticket {ticket_id} not found"
                elif e.response.status_code == 401:
                    error_msg = "Authentication failed - please check your credentials"
            return error_msg
