import logging
import traceback
from datetime import datetime

import requests
from botbuilder.core import TurnContext
from teams import Application as TeamsApplication
from teams.feedback_loop_data import FeedbackLoopData

from src.bots.data_model.app_state import AppTurnState
from src.config.settings import (
    atlassian_api_token,
    atlassian_confluence_url,
    atlassian_user,
)
from src.constants.app_constants import MIME_TYPE

_logger = logging.getLogger(__name__)


def register_feedback_handler(bot_app: TeamsApplication) -> None:
    """Register feedback handler for the bot application."""

    # Custom feedback loop
    @bot_app.feedback_loop()
    async def feedback_loop(
        _context: TurnContext,
        _state: AppTurnState,
        feedback_loop_data: FeedbackLoopData,
    ) -> None:
        _ = _state
        try:
            # Extract feedback data using the new data structure
            reaction = feedback_loop_data.action_value.reaction
            feedback_text = ""

            # Handle different types of feedback
            if isinstance(feedback_loop_data.action_value.feedback, str):
                feedback_text = feedback_loop_data.action_value.feedback
            elif isinstance(feedback_loop_data.action_value.feedback, dict):
                # Extract text from dictionary if available
                feedback_text = str(feedback_loop_data.action_value.feedback)

            # Format content
            content = f" Feedback: {feedback_text}"
            user_name = _context.activity.from_property.name if _context.activity.from_property else "Anonymous"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Fetch bot message that's reacted to
            bot_message_id = feedback_loop_data.reply_to_id

            bot_message = bot_message_id if bot_message_id else "Unknown"
            # Confluence page information
            page_id = "3457515623"  # Page ID of the feedback table

            # Fetch current page content
            response = requests.get(
                f"{atlassian_confluence_url}/rest/api/content/{page_id}?expand=body.storage,version",
                auth=(atlassian_user, atlassian_api_token),
            )

            if response.status_code != 200:
                _logger.error("Failed to fetch page content: %s, %s", response.status_code, response.text)
                return

            page_data = response.json()
            current_content = page_data["body"]["storage"]["value"]
            current_version = page_data["version"]["number"]

            # Add new row to the table
            # Find the closing </tbody> tag and insert our new row before it
            new_row = f"""
            <tr>
                <td>{timestamp}</td>
                <td>{user_name}</td>
                <td>{reaction}</td>
                <td>{content}</td>
                <td>{bot_message}</td>
            </tr>
            """

            if "</tbody>" in current_content:
                updated_content = current_content.replace("</tbody>", f"{new_row}</tbody>")
            else:
                # If no table exists yet raise error
                _logger.error("Failed to find table in Confluence page")
                return

            # Update the page content
            update_data = {
                "version": {"number": current_version + 1},
                "title": page_data["title"],
                "type": "page",
                "body": {"storage": {"value": updated_content, "representation": "storage"}},
            }

            update_response = requests.put(
                f"{atlassian_confluence_url}/rest/api/content/{page_id}",
                json=update_data,
                auth=(atlassian_user, atlassian_api_token),
                headers={"Content-Type": MIME_TYPE},
            )

            if update_response.status_code != 200:
                _logger.error("Failed to update page: %s, %s", update_response.status_code, update_response.text)
            else:
                _logger.info("Added feedback to Confluence success. Status: %s", update_response.status_code)
                await _context.send_activity("Thank you for your feedback! It helps us improve and serve you better.")

        except Exception as e:
            _logger.error("Error occurred: log feedback to Atlassian: %s", str(e))
            traceback.print_exc()
