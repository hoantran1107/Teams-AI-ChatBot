import logging
import traceback

from botbuilder.core import MessageFactory, TurnContext
from botbuilder.schema import Attachment
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from teams.streaming import StreamingResponse

from src.adaptive_cards.card_utils import create_error_card, send_adaptive_card
from src.bots.data_model.app_state import AppTurnState
from src.constants.app_constants import AdaptiveCardConst
from src.constants.llm_constant import AZURE_LLM03
from src.services.jira_sentiment_agentic.services.jira_services import JiraService

_logger = logging.getLogger(__name__)


def create_comprehensive_ticket_review_prompt(ticket_details: dict, draft_message: str) -> str:
    """Create a comprehensive prompt for both sentiment analysis and alternative suggestion generation.

    for a customer support ticket. The prompt requests a concise, structured review and improvement recommendations.
    """
    return f"""
As a customer support team member, please perform the following tasks for the ticket below:

---

**TICKET DETAILS:**
{ticket_details}

**DRAFT RESPONSE:**
**{draft_message}**

---

### 1. Sentiment Analysis

Please provide a concise, structured analysis including:

1. **Overall Sentiment:**
   - Determine the general sentiment expressed in the ticket (e.g., positive, neutral, negative) and give a brief explanation.

2. **Tone & Sentiment of Comments:**
   - Analyze the tone and specific sentiment of the ticket details comment—note if it feels empathetic, frustrated, appreciative, etc.

3. **Customer Concerns Addressed:**
   - Assess whether the draft response and ticket details comment appropriately acknowledge and address the customer's main concerns. If not, identify any gaps.

4. **Estimated Customer Satisfaction (%)** (with emoji highlight):
   - 🟢 **Customer Satisfaction Estimate:** **[your estimate]%**

5. **Ticket Details Analysis:**
   - Provide a brief analysis of the ticket details and context.

---

### 2. Alternative Suggestions (ONLY IF NEEDED)

- **If the Draft Response is already good, DO NOT provide any suggestions.**
- **If improvements are needed, provide 2-3 alternative response suggestions that are more empathetic, customer-focused, and solution-oriented.**

For EACH alternative suggestion, do the following:

1. **Explain why your suggestion is an improvement** over the original draft.
2. **Highlight key changes in tone, language, or approach in bold**.
3. **Keep the core message intact, but make it more customer-centric**.
4. **Check and correct English grammar and spelling**.
5. **Compare the tone of the draft response with the tone in the ticket details**; if the draft does not match, explain how your suggestion adjusts the tone appropriately.
6. **Estimate the customer satisfaction rate (%)** for the original draft using:
   🟢 **Customer Satisfaction Estimate:** **[your estimate]%**
7. **Rate the suitability (%) of the original draft response:**
   🔴 **Original Draft Suitability:** **[your estimate]%**
8. After each suggestion, include two sections:
    - **Content Evaluation:**
      - **Always show the Original Draft Response here (in bold).**
      - Critically analyze its strengths and weaknesses.
    - **Improved Response Suggestions:**
      - Offer your improved, alternative suggestion(s), with key improvements highlighted in bold.

---

**Formatting Instructions:**

- **Always show the Original Draft Response at the start of your response.**
- **Use emojis (🟢, 🔴) to highlight percentage scores for satisfaction and suitability.**
- **Highlight all key changes, your suggestions, and the original draft response in bold (use `**`).**
- **Number and clearly separate each suggestion.**
- **Include short, actionable explanations for every change you make.**
- **Use bullet points or sub-sections for clarity.**
- **Keep your response concise:** Limit each suggestion and explanation to the essentials. Avoid long paragraphs and unnecessary details.
- **All explanations and suggestions must be in English.**
- **Note:** All bolded text and emoji highlights are important—these help you quickly spot the key differences and improvements.

If you need more context or clarification (e.g., if ticket details are unclear), please state what additional information would be helpful at the end of your response.
"""


async def stream_reponse(context: TurnContext, prompt: str) -> None:
    """Stream the response from the LLM."""
    try:
        # Create the messages for the LLM
        messages = [
            SystemMessage(
                content="You are a helpful support team assistant specializing in sentiment analysis and response optimization.",
            ),
            SystemMessage(content=prompt),
        ]
        streamer = StreamingResponse(context)
        streamer.set_feedback_loop(True)
        streamer.set_generated_by_ai_label(True)

        streamer.queue_informative_update("🔍 Analyzing your draft response...\n\n")
        # Create the chain with the LLM
        chain = ChatPromptTemplate.from_messages(messages) | AZURE_LLM03
        async for chunk in chain.astream({"messages": messages}):
            if chunk.content:
                streamer.queue_text_chunk(str(chunk.content))
        await streamer.end_stream()

    except Exception as e:
        _logger.error("Error in stream_reponse: %s", traceback.format_exc())
        await context.send_activity(f"❌ Error during analysis: {e!s}")


async def handle_draft_submission(context: TurnContext, state: AppTurnState) -> None:
    """Handle the submission of a draft response for sentiment analysis."""
    _ = state  # Unused variable, but kept for consistency with other handlers
    if not hasattr(context.activity, "value") or not isinstance(context.activity.value, dict):
        card = create_error_card(title="Invalid Submission", message="Invalid submission format")
        await send_adaptive_card(context, card)
        return

    draft_message = context.activity.value.get("draft_message", "")
    ticket_id = context.activity.value.get("ticket_key", "")

    if not draft_message:
        card = create_error_card(title="Missing Draft Message", message="No draft message provided")
        await send_adaptive_card(context, card)
        return

    if not ticket_id:
        card = create_error_card(title="Missing Ticket ID", message="No ticket ID provided")
        await send_adaptive_card(context, card)
        return

    try:
        # Get ticket details
        ticket_details = JiraService().get_ticket_details(ticket_id)
        if type(ticket_details) is not dict:
            card = create_error_card(title="Error Fetching Ticket Details", message=ticket_details)
            await send_adaptive_card(context, card)
            return

        suggestions_prompt = create_comprehensive_ticket_review_prompt(ticket_details, draft_message)
        await stream_reponse(context, suggestions_prompt)
        return

    except Exception as e:
        _logger.error("Error processing draft: %s", traceback.format_exc())
        card = create_error_card(title="Error Processing Draft", message=str(e))
        await send_adaptive_card(context, card)
        return
