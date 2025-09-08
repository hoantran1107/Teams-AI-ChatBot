from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate

from src.constants.llm_constant import AZURE_LLM00
from src.services.postgres.models.tables.rag_sync_db.conversation_instructions import ConversationInstructions
from src.services.rag_services.models.graph_builder.models.update_instruction_model import (
    AllUpdatedInstructions,
)
from src.services.rag_services.models.graph_builder.prompts import (
    SAVE_INSTRUCTIONS_PROMPT,
)

INSTRUCTION_SET_PATTERN = """
- Name: {name}
  Purpose: {purpose}
  Current instructions:
  ```
{instructions}
  ```"""


def get_instruction_prompts(namespace, format_as_bullet_points=False):
    """
    Retrieves a list of instruction prompts for a given namespace.

    Args:
            namespace (tuple): A tuple representing the namespace for the instructions.
            format_as_bullet_points (bool, optional): If True, formats the instructions as bullet points. Defaults to False.

    Returns:
            list: A list of dictionaries, each containing the name, instructions, and purpose of an instruction set.
    """

    def get_procedural_memory(namespace, key, default_value=None):
        stored_value = ConversationInstructions.get(namespace, key)
        return (
            stored_value.value.get("instructions", default_value)
            if stored_value
            else default_value
        )

    prompts = [
        {
            "name": "interaction_instruction",
            "instructions": get_procedural_memory(
                namespace,
                "interaction_instruction",
                [
                    "Use polite, professional tone",
                    "Present content concisely, get straight to the point",
                    "Arrange ideas in priority order, most important first",
                ],
            ),
            "purpose": (
                "Defines how communication and content presentation should be when others write to me. This "
                "instruction set controls tone, formatting, length, structure, and other stylistic elements in all "
                "texts or messages sent to me, helping the sender convey information in the way I prefer to receive "
                "it"
            ),
        },
        {
            "name": "user_context",
            "instructions": get_procedural_memory(namespace, "user_context", []),
            "purpose": (
                "Provides personal and professional information about me for others to reference when communicating. "
                "This instruction set helps the sender understand my role, qualifications, interests, and personal "
                "context, allowing them to adjust content and approach appropriately, avoiding misunderstandings or "
                "misrepresentations about my identity and position."
            ),
        },
    ]

    if format_as_bullet_points:
        for prompt in prompts:
            prompt["instructions"] = _convert_to_bullet_points(prompt["instructions"])

    return prompts


def _convert_to_bullet_points(instructions):
    if isinstance(instructions, str):
        return instructions
    result = ""
    for idx, item in enumerate(instructions):
        if idx != len(instructions) - 1:
            result += f"  - {item}\n"
        else:
            result += f"  - {item}"
    return result


def format_instruction_sets(prompts):
    instruction_sets = [
        INSTRUCTION_SET_PATTERN.format(
            name=prompt["name"],
            purpose=prompt["purpose"],
            instructions=_convert_to_bullet_points(prompt["instructions"]),
        )
        for prompt in prompts
    ]
    return (
        "\n\n".join(instruction_sets)
        if instruction_sets
        else "No instruction sets found."
    )


def save_instruction_prompts(conversation_id, user_message, histories=None):
    """
    Saves updated instruction prompts for a user based on their feedback and conversation history.

    Args:
            conversation_id (str): The unique identifier of the conversation.
            user_message (str): The latest message from the user.
            histories (list): A list of previous chat messages.

    Returns:
        (AllUpdatedInstructions|None): An object containing the updated prompts if feedback is detected and
        processed. If no feedback is detected or if `user_id` is not provided, returns None.
    """
    if not conversation_id:
        return None
    if not histories:
        histories = []

    # Fetch the current instruction prompts for the user
    namespace = define_namespace_of_instructions(conversation_id)
    prompts = get_instruction_prompts(namespace)

    write_instruction_llm = AZURE_LLM00.with_structured_output(AllUpdatedInstructions)
    format_chat_history_ = "\n\n".join(
        msg.pretty_repr() for msg in histories + [HumanMessage(content=user_message)]
    )
    chain = (
        PromptTemplate(
            template=SAVE_INSTRUCTIONS_PROMPT,
            input_variables=["instruction_sets", "chat_history", "user_message"],
        )
        | write_instruction_llm
    )
    response: AllUpdatedInstructions = chain.invoke(
        {
            "instruction_sets": format_instruction_sets(prompts),
            "chat_history": format_chat_history_,
            "user_message": user_message,
        }
    )

    # Update the stored prompts with the new values
    for item in response.updates:
        found_item = next(p for p in prompts if p["name"] == item.name)
        ConversationInstructions.put(
            namespace,
            item.name,
            {**found_item, "instructions": item.updated_instruction},
        )

    return response


def define_namespace_of_instructions(conversation_id):
    """
    Defines the namespace for storing instruction prompts.

    Args:
        conversation_id (str): The unique identifier of the conversation.

    Returns:
        tuple: A tuple containing the conversation ID and the string "instructions".
    """
    return conversation_id, "instructions"
