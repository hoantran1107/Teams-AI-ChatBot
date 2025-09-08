import logging

from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.config.settings import atlassian_jira_url
from src.services.custom_llm.services.llm_utils import LLMUtils
from src.services.jira_services.services.get_data import (
    add_comment_to_ticket,
    get_all_field,
    get_content_jira,
)
from src.services.jira_services.services.jira_utils import extract_context_data

logger = logging.getLogger(__name__)

# Centralized tokens to avoid literal duplication
MODIFY_PREFIX = "modify:"
NO_MODIFY_MARKER = "no_modify"  # marker string used in LLM parsing; not a secret


async def handle_confirm_jira_comment(context: TurnContext, state: AppTurnState) -> str:
    """Handle confirmation for Jira comment using AI to understand user response."""
    result_message = None
    try:
        pending_comment = state.conversation.get("pending_comment")
        if not pending_comment:
            await context.send_activity("❌ **Error**: No pending comment to confirm.")
            result_message = "No pending comment"
        else:
            user_response = context.activity.text
            confirmation_result = await _check_confirmation_intent(user_response)

            if confirmation_result == "confirm":
                result = await add_comment_to_ticket(
                    pending_comment["ticket_key"],
                    pending_comment["comment_text"],
                )
                if result.get("success"):
                    response = await _generate_ai_response(
                        pending_comment["ticket_key"],
                        pending_comment["comment_text"],
                        pending_comment["comment_type"],
                        result,
                        pending_comment["summary"],
                        pending_comment["status"],
                    )
                    ticket_link = f"{atlassian_jira_url}/browse/{pending_comment['ticket_key']}"
                    response_with_link = f"{response}\n\n🔗 **View Ticket**: {ticket_link}"
                    await context.send_activity(response_with_link)
                    result_message = f"Comment confirmed and added to {pending_comment['ticket_key']}"
                else:
                    error_message = result.get("message", "Unknown error occurred")
                    await context.send_activity(f"❌ **Error**: {error_message}")
                    result_message = f"Failed to add comment: {error_message}"
                state.conversation.pending_comment = None

            elif confirmation_result == "cancel":
                await context.send_activity("❌ **Comment cancelled**. No comment was added.")
                state.conversation.pending_comment = None
                result_message = "Comment cancelled by user"

            else:
                modification_result = await _check_modification_intent(user_response, pending_comment["comment_text"])
                if modification_result["should_modify"]:
                    new_comment_text = modification_result["new_text"]
                    formatted_comment = _format_jira_comment(new_comment_text, pending_comment["comment_type"])
                    state.conversation.pending_comment["comment_text"] = formatted_comment
                    confirmation_message = f"""
                            🤔 **Confirm Comment on Jira Ticket**

                            **Ticket**: {pending_comment["ticket_key"]}
                            **Summary**: {pending_comment["summary"]}
                            **Status**: {pending_comment["status"]}
                            **Comment Type**: {pending_comment["comment_type"]}
                            **Comment**: {formatted_comment}

                            **Is this correct?** Please confirm with:
                            - "Yes" or "Correct" to proceed
                            - "No" or "Cancel" to abort
                            - Or provide corrections"""
                    await context.send_activity(confirmation_message)
                    result_message = "Updated comment and waiting for confirmation"
                else:
                    await context.send_activity(
                        "🤔 I didn't understand your response. Please say 'Yes' to confirm, "
                        "'No' to cancel, or provide a new comment text.",
                    )
                    result_message = "Waiting for clear confirmation"

    except (ConnectionError, TimeoutError, ValueError, AttributeError) as e:
        logger.error("Error in handle_confirm_jira_comment: %s", e)
        await context.send_activity("❌ **Error**: An unexpected error occurred during confirmation.")
        result_message = "Error during confirmation: " + str(e)
    return result_message


async def _check_confirmation_intent(user_response: str) -> str:
    """Use AI to understand user's confirmation intent."""
    try:
        context = f"""
        Analyze this user response to determine if they are confirming or cancelling an action.  
        User response: "{user_response}"

        Determine if the user is:
        1. Confirming (saying yes, agreeing, approving)
        2. Cancelling (saying no, disagreeing, rejecting)
        3. Unclear (ambiguous response)

        Return only: "confirm", "cancel", or "unclear"
        """

        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(context)

        # Clean the response
        if isinstance(response.content, list):
            result = " ".join(str(item) for item in response.content).strip().lower()
        else:
            result = str(response.content).strip().lower()

        if "confirm" in result:
            return "confirm"
        if "cancel" in result:
            return "cancel"
        return "unclear"

    except Exception as e:
        logger.error(f"Error in _check_confirmation_intent: {e}")
        # If AI fails, return unclear to let user clarify
        return "unclear"


async def _check_modification_intent(user_response: str, current_comment: str) -> dict:
    """Simplified modification check via one-shot LLM call."""
    try:
        prompt = f"""
        Current comment: "{current_comment}"
        User input: "{user_response}"

        Decide if the user wants to modify the comment.
        If yes, return "{MODIFY_PREFIX} new comment here"
        If no, return "{NO_MODIFY_MARKER}"
        """
        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(prompt)
        if response and hasattr(response, "content"):
            content = response.content.strip().lower()
            if content.startswith(MODIFY_PREFIX):
                return {"should_modify": True, "new_text": content[len(MODIFY_PREFIX) :].strip()}
            if content.startswith(NO_MODIFY_MARKER):
                return {"should_modify": False, "new_text": ""}

        return {"should_modify": False, "new_text": ""}

    except Exception as e:
        logger.error(f"Error in _check_modification_intent: {e}")
        return {"should_modify": False, "new_text": ""}


async def _analyze_modification_response(ai_response: str) -> dict:
    """Use AI to analyze the modification response."""
    try:
        context = f"""
        Analyze this AI response to determine if it indicates a modification request.
        
        AI response: "{ai_response}"
        
        Determine if this response:
        1. Indicates the user wants to modify the comment
        2. Indicates the user does not want to modify
        
        If it indicates modification, extract the new comment text.
        
        Return only: "{MODIFY_PREFIX} new text" or "{NO_MODIFY_MARKER}"
        """  # noqa: W293

        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(context)

        # Use AI again to parse the final response
        final_analysis = await _parse_modification_result(response.content)
        return final_analysis

    except Exception as e:
        logger.error(f"Error in _analyze_modification_response: {e}")
        return {"should_modify": False, "new_text": ""}


async def _parse_modification_result(ai_response: str) -> dict:
    """Use AI to parse the final modification result."""
    try:
        context = f"""
        Parse this response to determine modification intent.
        
        Response: "{ai_response}"
        
        If this indicates modification, extract the new text.
        Otherwise, indicate no modification.
        
        Return only: "{MODIFY_PREFIX} new text" or "{NO_MODIFY_MARKER}"
        """  # noqa: W293

        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(context)

        # Use AI to understand the final result
        final_result = await _understand_final_result(response.content)
        return final_result

    except Exception as e:
        logger.error(f"Error in _parse_modification_result: {e}")
        return {"should_modify": False, "new_text": ""}


async def _understand_final_result(ai_response: str) -> dict:
    """Use AI to understand the final result without any hard-coded logic."""
    try:
        context = f"""
        Understand this response and determine if it indicates a modification.
        
        Response: "{ai_response}"
        
        If this response indicates the user wants to modify the comment, extract the new text.
        Otherwise, indicate no modification.
        
        Return only: "{MODIFY_PREFIX} new text" or "{NO_MODIFY_MARKER}"
        """  # noqa: W293

        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(context)

        # Use AI one more time to make the final decision
        final_decision = await _make_final_decision(response.content)
        return final_decision

    except Exception as e:
        logger.error(f"Error in _understand_final_result: {e}")
        return {"should_modify": False, "new_text": ""}


async def _make_final_decision(ai_response: str) -> dict:
    """Use AI to make the final decision without any hard-coded parsing."""
    try:
        context = f"""
        Make the final decision about modification based on this response.
        
        Response: "{ai_response}"
        
        If this indicates modification, return the new text.
        Otherwise, indicate no modification.
        
        Return only: "{MODIFY_PREFIX} new text" or "{NO_MODIFY_MARKER}"
        """  # noqa: W293

        llm = LLMUtils.get_azure_openai_llm()
        # Let AI make the final decision without any hard-coded logic
        response = await llm.ainvoke(context)
        if response and hasattr(response, "content"):
            content = response.content.strip()
            lower_content = content.lower()
            if lower_content.startswith(MODIFY_PREFIX):
                # Extract the new text after the modify token
                new_text = content[len(MODIFY_PREFIX) :].strip()
                return {"should_modify": True, "new_text": new_text}
            if lower_content == NO_MODIFY_MARKER:
                return {"should_modify": False, "new_text": ""}

        # If AI fails or returns unexpected output, return no modification as safe default
        return {"should_modify": False, "new_text": ""}

    except Exception as e:
        logger.error(f"Error in _make_final_decision: {e}")
        return {"should_modify": False, "new_text": ""}


def _format_jira_comment(comment_text: str, comment_type: str | None = None) -> str:
    """Format comment for better presentation in Jira.

    Args:
        comment_text: The text of the comment to format
        comment_type: Optional type of comment for context

    Returns:
        The formatted comment text with footer

    """
    # Clean up the comment text while preserving original formatting
    cleaned_text = _clean_comment_text(comment_text)

    # Use the original text exactly as provided by user
    # Add the footer with type if provided
    footer = f"*Added via AI Assistant ({comment_type})*" if comment_type else "*Added via AI Assistant*"
    formatted = f"{cleaned_text}\n\n---\n{footer}"

    return formatted


def _clean_comment_text(text: str) -> str:
    """Clean up comment text while preserving original formatting."""
    # Keep the original text exactly as provided by user
    # Only remove excessive line breaks at the end
    cleaned_text = text.rstrip()

    # Ensure consistent spacing between sections (max 2 line breaks)
    cleaned_text = cleaned_text.replace("\n\n\n", "\n\n")
    cleaned_text = cleaned_text.replace("\n\n\n", "\n\n")

    return cleaned_text


async def _generate_ai_response(  # noqa: PLR0913
    ticket_key: str,
    comment_text: str,
    comment_type: str,
    result: dict,
    summary: str,
    status: str,
) -> str:
    """Generate a natural conversational response using AI only - no hard coding.

    Args:
        ticket_key: The key of the Jira ticket
        comment_text: The text of the comment
        comment_type: The type of comment (e.g., "approval", "feedback")
        result: Dictionary containing comment submission results
        summary: The ticket summary
        status: The ticket status

    Returns:
        A natural language response confirming the comment was added

    """
    comment_id = result.get("comment_id", "N/A")
    author = result.get("author", "Unknown")

    # Create direct link to the comment using atlassian_jira_url from top of file
    comment_link = (
        f"{atlassian_jira_url}/browse/{ticket_key}?focusedCommentId={comment_id}&"
        f"page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-{comment_id}"
    )

    try:
        # Create context for AI with natural conversation style
        context = (
            f"I just added a comment to Jira ticket {ticket_key}.\n\n"
            f"Context:\n"
            f"- Ticket: {ticket_key} ({summary})\n"
            f"- Status: {status}\n"
            f"- Comment Type: {comment_type}\n"
            f"- Comment: {comment_text}\n"
            f"- Comment ID: {comment_id}\n"
            f"- Author: {author}\n\n"
            "Generate a brief, natural acknowledgment. Keep it casual and friendly.\n"
            "Don't be formal or repetitive. Just acknowledge the action simply.\n"
            "Keep it under 2 sentences. No need to ask if they need anything else.\n"
            "Make it sound like a real person talking to a colleague.\n"
            "Do NOT include any links in your response."
        )

        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(context)

        # Add only the direct comment link
        return f"{response.content}\n\n🔗 **View Comment**: {comment_link}"

    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Azure OpenAI connection error: {e}")
        # Connection issues - minimal fallback
        return f"✅ Comment added to {ticket_key}\n\n🔗 **View Comment**: {comment_link}"
    except (ValueError, AttributeError) as e:
        logger.error(f"Error parsing AI response: {e}")
        # Response parsing issues - minimal fallback
        return f"✅ Comment added to {ticket_key}\n\n🔗 **View Comment**: {comment_link}"


async def handle_submit_jira_comment(context: TurnContext, state: AppTurnState) -> str:
    """Legacy handler for adaptive card submission - kept for backward compatibility."""
    return await handle_comment_jira_ticket(context, state)


async def handle_cancel_comment(context: TurnContext) -> str:
    """Handle cancellation of comment action."""
    await context.send_activity("❌ **Comment cancelled**. No comment was added.")
    return "Comment action cancelled."
