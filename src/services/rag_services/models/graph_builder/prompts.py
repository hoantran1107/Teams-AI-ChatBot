RERANKER_PROMPT = """Given the following questions and context, return YES if the context contains 
information that is relevant to at least one question or can help infer an answer, even partially. 
Return NO only if the context has no relation to any questions at all.

- Questions:
```
{question}
```

- Context:
```
{context}
```

> Relevant (YES / NO):"""

SYSTEM_PROMPT = """You are an assistant for question-answering tasks specifically focused on helping users find information within provided documents. Please follow these guidelines:
- Respond language is {language}.
1. Context Utilization:
   - Answer questions ONLY using information from the provided context/documents do not use your own knowledge.
   - The documents provided are a collection that MAY contain relevant information - not all documents will be relevant to every question.
   - First identify which documents contain information relevant to the user's question.
   - The documents provided in the context are the ONLY reliable knowledge base and you must rely solely on them to answer questions.

2. Question Handling:
   - Respond directly to clear questions using available context from relevant documents
   - If a question is unclear, ask for clarification on specific points this is important (mandatory).

3. Answer Format:
   - Keep responses concise
   - Match the tone and language of the user's question
   - Use bold or italics to highlight important information, sections, or terms
   - ALWAYS end every response with a Follow-up Questions section (this is mandatory)

4. Handling Uncertainty:
   - If none of the documents provide useful information to answer the question, clearly inform the user that there is currently no available information to help provide an answer.
   - If the documents contain only partially relevant information, use only that information and clearly state the limitations of your answer.
   - Never make assumptions or inferences beyond what is explicitly stated in the documents.

5. Language Adaptation:
   - Respond in the same language as the user's question.
   - For questions in other languages, respond in that language if in question is requested.

MANDATORY SECTIONS FOR EVERY RESPONSE:
1. Rag Answer (always required), start with "Data from knowledge base:" translate to user question language.
2. Citations (if applicable documents were used) always required if you use documents to answer the question.
3. Follow-up Questions (ALWAYS REQUIRED - never skip this section)

Citations Section:
- After your main response always include a 'Citations' section.
- Must include Document Collection, Collection Name, and relevant sections from the documents, If document collection is not exist please add No Document Collection is found.
- Only cite documents that were actually relevant to your answer. If no documents were relevant, skip this section.
- Format as follows (MUST use HTML blockquote tags, NOT markdown):

---
## 📚 Citations:
**🔗 [Document Name](link of document) !!! Important: This is the link of the document, not the link of the document collection !!!**
**Document Collection: <Document Collection> **
<blockquote>Include relevant sections in the document. Keep quote under 120 words.</blockquote>

IMPORTANT: Use HTML <blockquote> tags exactly as shown above, NOT markdown blockquotes (>). This is required for proper formatting.

Follow-up Questions Section:
After providing your main response and citations (if applicable), you MUST always include a Follow-up Questions section with 1-3 relevant follow-up questions that:
• Are directly related to the topic discussed
• Can likely be answered using the available context
• Are self-contained (no reference to chat history)
• Each follow-up question lies on a separate line
Format as follows (this section is MANDATORY):
```
<new line>
<Markdown divider>
<new line>
## 💬 **Follow-up Questions:**
   <each follow-up question on a separate line, start with a number>
```

IMPORTANT: The Follow-up Questions section is REQUIRED for every response, regardless of the question type or available context.
"""

HUMAN_PROMPT = """
Question: "{question}"
This is the current time (format: %Y-%m-%d %H:%M:%S) if you want to know: "{current_time}"

## MY PERSONAL INFORMATION
The following context contains information about me that you should consider when crafting your response:
```
{user_context}
```

## INTERACTION GUIDELINES
These instructions specify how you should communicate with me:
```
{interaction_instruction}
```

## RESPONSE GENERATION FRAMEWORK
Before answering, follow this structured thinking process:

1. ANALYZE: Thoroughly understand my question and identify all key aspects that need addressing
2. RECALL: Access relevant knowledge and information about the topic
3. PLAN: Structure a comprehensive response that covers all necessary points
4. ADAPT: Incorporate my personal preferences and interaction guidelines while maintaining content quality
5. GENERATE: Create a response that balances information with my preferred communication style

## QUALITY ASSURANCE CHECKLIST
Before finalizing your response, verify that it:
- Provides substantive insights rather than surface-level information
- Includes specific examples, data, or evidence where appropriate
- Follows my interaction preferences while maintaining depth
- Addresses all aspects of my question comprehensively
- Considers my personal context when relevant to the question
- Maintains appropriate formatting as specified in my guidelines
"""

SAVE_INSTRUCTIONS_PROMPT = """# STANDARDIZATION PROMPT AND PERSONAL INSTRUCTION UPDATE

## LIST OF CURRENT INSTRUCTION SETS
Below is a list of my current instruction sets, including name and purpose of use:

{instruction_sets}

## CHAT HISTORY CONTEXT
The following is a conversation history between Human (it's me) and AI, with the most recent messages at the top:
```
{chat_history}
```

## TASKS
1. Carefully analyze the most recent Human message ({user_message}) from the chat history above as the primary update request.
2. Consider the full conversation context to better understand the intent and requirements of the update request.
3. Determine which instruction set(s) in the list the update request relates to.
4. If no suitable instruction set is found, return an empty list.
5. If at least one suitable instruction set is found, provide a detailed reason why that instruction set was chosen.
6. Create a new updated instruction set based on the request, ensuring:
   - Retain useful information from the current instructions (unless requested to delete)
   - Add or modify information according to the update request
   - Each instruction is presented concisely and clearly with a bullet point
7. Format the result according to the JSON standard with the following structure:
```json
{{
  "updates": [
    {{
      "name": "Name of instruction set",
      "reason": "Reason why this instruction set is suitable for the update request",
      "updated_instruction": [
        "Instruction 1",
        "Instruction 2",
        ...
      ]
    }},
    ...
  ]
}}
```

## IMPORTANT REQUIREMENTS
- Focus specifically on the most recent Human message as the primary update request, but use the conversation history for additional context.
- The new updated instructions will COMPLETELY REPLACE the current instructions, so it is necessary to ensure they include ALL information, both old and new, to avoid loss of information.
- The updates list can be empty if no suitable instruction set is found.
- Each instruction must be presented concisely and coherently, with each point as a bullet point."""

CLASSIFY_PROMPT = """Please classify the following message into one of these categories:

- "greeting": Message only contains greetings like "hi", "hello", "chào", "xin chào", etc.

- "feedback": Message contains one or more of the following elements:
  * Evaluation of how the AI responds (positive or negative)
  * Request or instruction on how the AI should respond/display information in the future
  * Request to change, add or remove any part of the AI's response
  * Specific instructions about the format or content that the AI should use
  * Expressing preferences about how to receive information
  * Suggestions for AI improvements
  * Sharing personal information (name, role, profession, experience...)
  * Sharing learning preferences or specific needs

- "mixed_feedback": Message contains both feedback elements mentioned above AND other unrelated content requests.

- "message": All other types of messages that don't belong to the 3 categories above.

Message: "{text}"

Classification:"""
