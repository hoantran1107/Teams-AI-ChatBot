from botbuilder.core import TurnContext

from src.bots.data_model.app_state import AppTurnState
from src.services.jira_services.services.get_citations import get_jiraticket_citations
from src.services.jira_services.services.get_data import get_all_field, get_content_jira
from src.services.jira_services.services.jira_utils import extract_context_data, send_response


async def handle_get_jira_ticket_info(context: TurnContext, state: AppTurnState) -> str | None:
    """Handle bot and adaptive card action get Jira ticket data."""
    ticket_context = await get_info_ticket(context)

    if not isinstance(ticket_context, list):
        return ticket_context
    ticket_ids, raw_contents, citations = ticket_context

    prompt_text = f"""
    You are tasked with generating a structured Markdown document to describe multiple Jira tickets based on provided raw content and user input.

    **Raw Content**:
    {raw_contents}

    **Task**:
    Format each ticket into a clear, professional Markdown document suitable for sprint reviews, Confluence reporting, or stakeholder communication, tailoring the focus and detail level based on the user input.

    **Instructions**:
    1. **Input Processing**:
    - Process each ticket's content separately from the provided raw content, which is a list of ticket data with ticket IDs.
    - If user input specifies a focus (e.g., 'summarize tickets', 'detailed description', 'bot-related tickets'), prioritize relevant content and adjust detail accordingly for all tickets.

    2. **Ticket Structure**:
    - For each ticket, include only sections with data in raw content or requested to be generated in user input:
        - **Ticket ID**: Extract from raw content; omit if missing.
        - **Summary**: Concise title from raw content or user input; omit if absent unless requested. 
        - **Status**: Current status (e.g., 'To Do', 'In Progress', 'Done'); omit if missing.
        - **Assignee**: Assigned person; omit if unspecified.
        - **Story Points**: Numeric value; omit if missing.
        - **Objective**: Ticket purpose; omit if not provided unless requested.
        - **Background**: Context; omit if not provided unless requested.
        - **Description**: Work details; omit if absent unless requested.
        - **Reason**: Why the ticket exists; omit if not provided unless requested.
        - **Acceptance Criteria**: Completion conditions; omit if not provided unless requested.
    - Use bullet points for multi-item sections (e.g., Description, Acceptance Criteria) and NO use bullet points for fields have one-item.

    - Always respond following the structure defined above and DO NOT add any additional other fields in the raw content of the response.

    3. **Content Customization**:
    - Adjust detail level based on user input:
        - If 'brief' or 'summary' is specified, limit Description and Acceptance Criteria to 1–2 bullets per ticket.
        - If 'detailed' is specified, provide comprehensive details, including technical aspects if relevant.
        - If no preference is given, aim for a balanced, scalable format (2–3 bullets per section where applicable).
    - Tailor tone and focus to the audience implied by input (e.g., technical for developers, high-level for stakeholders).
    - If input specifies a focus (e.g., 'bot enhancements'), highlight relevant details for each ticket.

    4. **Error Handling**:
    - If raw content is missing critical fields for a ticket (e.g., Summary, Description), infer reasonable values from available data or user input, noting assumptions (e.g., 'Inferred from summary').
    - If no tickets are found or content is invalid, return a message: 'No valid tickets found.'
    - If a ticket ID in input doesn't match raw content, note: 'Requested ticket ID {{ticket_id}} not found in raw content.'

    5. **Output Format**:
    - Use Markdown with clear headings (### for each ticket, bold for section titles).
    - Separate multiple tickets with a blank line and a horizontal rule (---).
    - Ensure content is concise, professional, and suitable for Confluence or sprint review.
    - If user input requests specific formatting (e.g., 'table for ticket details'), incorporate as feasible.
    - Do not wrap the entire output in ```markdown``` blocks.
    - List tickets in the order of provided ticket IDs, with each ticket under its own heading (e.g., ### Ticket {{ticket_id}}).

    6. **References**: {citations}
    - If citations are provided as a list of dictionaries (with 'position' and 'url'), include a **References** section at the end of the entire document.
    - Format references as a single line: **References** [¹](url1) [²](url2) ...
    - Each reference number (e.g., [¹]) must be a clickable hyperlink to the corresponding URL.
    - If no citations are provided or the list is empty, omit the **References** section.
    - Do not insert reference numbers (e.g., [¹]) within the main content (e.g., Description).
    """

    user_content = "Describe tickets " + ", ".join(ticket_ids)
    return await send_response(context, state, prompt_text, user_content)


async def _process_ticket_data(tickets_id: list) -> str | list:
    """Process multiple ticket data and return formatted content for all tickets."""
    formatted_contents = []
    valid_tickets = []
    tickets = []
    all_issue_fields = await get_all_field()
    for ticket_id in tickets_id:
        tickets.append(ticket_id)
        ticket_data_dict = await get_content_jira(ticket_id, all_issue_fields)

        if not ticket_data_dict or ticket_id not in ticket_data_dict:
            formatted_contents.append(
                f"### Ticket {ticket_id}: Could not retrieve details."
                f"The ticket {ticket_id} incorrect .",
            )
            continue

        ticket_data = ticket_data_dict[ticket_id]

        valid_tickets.append(ticket_id)
        formatted_contents.append(f"### Ticket {ticket_id}:\n{ticket_data}")

    contents = "\n".join(formatted_contents)
    if not valid_tickets:
        return contents

    # Get citations for all ticket IDs
    citations = get_jiraticket_citations(valid_tickets)

    return [tickets, contents, citations]


async def get_info_ticket(context: TurnContext) -> str | list:
    """Get Jira ticket Data."""
    tickets_id = extract_context_data(context, ["tickets"])[0]

    if not tickets_id:
        return "No valid Jira link or ticket key found."

    return await _process_ticket_data(tickets_id)
