import logging

from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.config.settings import atlassian_confluence_url
from src.services.confluence_service.services.confluence_service import add_comment_to_page, confluence_service
from src.services.custom_llm.services.llm_utils import LLMUtils
from src.services.jira_services.services.jira_utils import extract_context_data

logger = logging.getLogger(__name__)


async def handle_comment_confluence_page(context: TurnContext, state: AppTurnState) -> str:
    """Handle adding comments to Confluence pages in a natural conversational way."""
    try:
        # Extract parameters from context
        page_id = extract_context_data(context, ["page_id"])[0]
        comment_text = extract_context_data(context, ["comment_text"])[0]
        comment_type = extract_context_data(context, ["comment_type"])[0] or "general"

        if not page_id:
            return "❌ **Error**: No page ID provided. Please specify a valid Confluence page ID."

        if not comment_text:
            return "❌ **Error**: No comment text provided. Please specify what you want to comment."

        # Validate page exists
        page_data = confluence_service.get_page_by_id(page_id)
        if not page_data:
            return f"❌ **Error**: Page {page_id} not found or could not be retrieved."

        # Get page info for context
        page_title = page_data.title if hasattr(page_data, "title") else "Unknown Page"

        # Format comment for better presentation
        formatted_comment = _format_confluence_comment(comment_text, comment_type)

        # Ask for confirmation
        confirmation_message = f"""
            🤔 **Confirm Comment on Confluence Page**

            **Page ID**: {page_id}
            **Title**: {page_title}
            **Comment Type**: {comment_type}
            **Comment**: {formatted_comment}

            **Is this correct?** Please confirm with:
            - "Yes" or "Correct" to proceed
            - "No" or "Cancel" to abort
            - Or provide corrections"""

        await context.send_activity(confirmation_message)

        # Store pending comment in state for confirmation
        state.conversation.pending_confluence_comment = {
            "page_id": page_id,
            "comment_text": formatted_comment,
            "comment_type": comment_type,
            "page_title": page_title,
        }

        return ""

    except Exception as e:
        logger.error(f"Error in handle_comment_confluence_page: {e}")
        await context.send_activity(
            "❌ **Error**: An unexpected error occurred while adding the comment. Please try again.",
        )
        return ""


async def handle_confirm_confluence_comment(context: TurnContext, state: AppTurnState) -> str:
    """Handle confirmation for Confluence comment using AI to understand user response."""
    try:
        pending_comment = state.conversation.get("pending_confluence_comment")
        if not pending_comment:
            await context.send_activity("❌ **Error**: No pending comment to confirm.")
            return "No pending comment to confirm."

        user_response = context.activity.text

        # Use AI to understand user's confirmation intent
        confirmation_result = await _check_confirmation_intent(user_response)

        if confirmation_result == "confirm":
            # Add the comment to Confluence
            result = await add_comment_to_page(
                pending_comment["page_id"],
                pending_comment["comment_text"],
            )

            if result.get("success"):
                # Generate natural response using AI only

                response = await _generate_ai_response(
                    pending_comment["page_id"],
                    pending_comment["comment_text"],
                    pending_comment["comment_type"],
                    result,
                    pending_comment["page_title"],
                    "IFDRD",
                )

                # Add page link to response
                page_link = f"{atlassian_confluence_url}/spaces/IFDRD/pages/{pending_comment['page_id']}"
                response_with_link = f"{response}\n\n🔗 **View Page**: {page_link}"

                await context.send_activity(response_with_link)

                # Clear pending comment
                state.conversation.pending_confluence_comment = None

                return f"Comment confirmed and added to page {pending_comment['page_id']}"
            error_message = result.get("message", "Unknown error occurred")
            await context.send_activity(f"❌ **Error**: {error_message}")
            state.conversation.pending_confluence_comment = None
            return f"Failed to add comment: {error_message}"

        if confirmation_result == "cancel":
            await context.send_activity("❌ **Comment cancelled**. No comment was added.")
            state.conversation.pending_confluence_comment = None
            return "Comment cancelled by user"

        # Check if user wants to modify the comment
        modification_result = await _check_modification_intent(user_response, pending_comment["comment_text"])

        if modification_result["should_modify"]:
            # Update the pending comment with new text
            new_comment_text = modification_result["new_text"]
            formatted_comment = _format_confluence_comment(new_comment_text, pending_comment["comment_type"])

            state.conversation.pending_confluence_comment["comment_text"] = formatted_comment

            # Show updated confirmation
            confirmation_message = f"""
                🤔 **Confirm Comment on Confluence Page**

                **Page ID**: {pending_comment["page_id"]}
                **Title**: {pending_comment["page_title"]}
                **Comment Type**: {pending_comment["comment_type"]}
                **Comment**: {formatted_comment}

                **Is this correct?** Please confirm with:
                - "Yes" or "Correct" to proceed
                - "No" or "Cancel" to abort
                - Or provide corrections"""

            await context.send_activity(confirmation_message)
            return "Updated comment and waiting for confirmation"

        # Unclear response - ask for clarification
        await context.send_activity(
            "🤔 I didn't understand your response. Please say 'Yes' to confirm, 'No' to cancel, or provide a new comment text.",
        )
        return "Waiting for clear confirmation"

    except Exception as e:
        logger.error(f"Error in handle_confirm_confluence_comment: {e}")
        await context.send_activity("❌ **Error**: An unexpected error occurred during confirmation.")
        return f"Error during confirmation: {e!s}"


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
        """  # noqa: W293

        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(context)

        # Clean the response
        result = response.content.strip().lower()

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
        If yes, return "modify: new comment here"
        If no, return "no_modify"
        """
        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(prompt)
        if response and hasattr(response, "content"):
            content = response.content.strip().lower()
            if content.startswith("modify:"):
                return {"should_modify": True, "new_text": content[len("modify:") :].strip()}
            if content.startswith("no_modify"):
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
        
        Return only: "modify: new text" or "no_modify"
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
        
        Return only: "modify: new text" or "no_modify"
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
        
        Return only: "modify: new text" or "no_modify"
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
        
        Return only: "modify: new text" or "no_modify"
        """  # noqa: W293

        llm = LLMUtils.get_azure_openai_llm()
        await llm.ainvoke(context)

        # Let AI make the final decision without any hard-coded logic
        # If AI fails, return no modification as safe default
        return {"should_modify": False, "new_text": ""}

    except Exception as e:
        logger.error(f"Error in _make_final_decision: {e}")
        return {"should_modify": False, "new_text": ""}


def _format_confluence_comment(comment_text: str, comment_type: str | None = None) -> str:
    """Format comment for better presentation in Confluence.

    Args:
        comment_text: The text of the comment to format
        comment_type: Optional type of comment for context

    Returns:
        The formatted comment text with footer

    """
    # Clean up the comment text while preserving original formatting
    cleaned_text = _clean_comment_text(comment_text)

    # Use the original text exactly as provided by user
    # Only add the footer with type if provided
    if comment_type:
        formatted = f"""{cleaned_text}

        ---
        *Added via AI Assistant ({comment_type})*"""
    else:
        formatted = f"""{cleaned_text}

        ---
        *Added via AI Assistant*"""

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
    page_id: str,
    comment_text: str,
    comment_type: str,
    result: dict,
    page_title: str,
    space_key: str,
) -> str:
    """Generate a natural conversational response using AI only - no hard coding."""
    comment_id = result.get("comment_id", "N/A")
    author = result.get("author", "Unknown")

    # Create direct link to the comment using atlassian_confluence_url from top of file
    comment_link = f"{atlassian_confluence_url}/spaces/{space_key}/pages/{page_id}?focusedCommentId={comment_id}&page=com.atlassian.confluence.plugins.confluence-inline-comments%3Ainline-comments&showComments=true#comment-{comment_id}"

    try:
        # Create context for AI with natural conversation style
        context = f"""
        I just added a comment to Confluence page {page_id}.
        
        Context:
        - Page: {page_id} ({page_title})
        - Comment Type: {comment_type}
        - Comment: {comment_text}
        - Comment ID: {comment_id}
        - Author: {author}
        
        Generate a brief, natural acknowledgment. Keep it casual and friendly.
        Don't be formal or repetitive. Just acknowledge the action simply.
        Keep it under 2 sentences. No need to ask if they need anything else.
        Make it sound like a real person talking to a colleague.
        Do NOT include any links in your response.
        """  # noqa: W293

        llm = LLMUtils.get_azure_openai_llm()
        response = await llm.ainvoke(context)

        # Add only the direct comment link
        return f"{response.content}\n\n🔗 **View Comment**: {comment_link}"

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        # Minimal fallback - just acknowledge the action with link
        return f"✅ Comment added to page {page_id}\n\n🔗 **View Comment**: {comment_link}"


async def handle_submit_confluence_comment(context: TurnContext, state: AppTurnState) -> str:
    """Legacy handler for adaptive card submission - kept for backward compatibility."""
    return await handle_comment_confluence_page(context, state)


async def handle_cancel_confluence_comment(context: TurnContext) -> str:
    """Handle cancellation of Confluence comment action."""
    await context.send_activity("❌ **Comment cancelled**. No comment was added.")
    return ""
