from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate

from src.services.custom_llm.models.grade_documents import GradeDocuments
from src.services.custom_llm.services.llm_utils import LLMUtils


class GradeDocumentsService:
	@staticmethod
	def grade_documents(question, documents: list[Document]):
		# Initialize the language model with structured output for grading
		llm = LLMUtils.get_azure_openai_llm().with_structured_output(GradeDocuments)

		# Prompt template for relevance grading
		system_prompt_template = (
			"You are a grader assessing relevance of a collection of retrieved documents to a "
			"user question. It does not need to be a stringent test. The goal is to filter out erroneous retrievals and "
			"keep only the retrieved documents which can be used as references to answer the user's question. For each "
			"document, if it contains keyword(s) or semantic meaning related to the user question, grade it as relevant."
			"\n\nGive a binary score 1 or 0 score to indicate whether a document in the collection is relevant to the question."
		)

		human_message_prompt_template = (
			"Collection of retrieved documents:"
			"\n{documents}"
			"\nUser question: {question}"
		)

		prompt = ChatPromptTemplate.from_messages(
			[
				SystemMessagePromptTemplate.from_template(system_prompt_template),
				HumanMessagePromptTemplate.from_template(human_message_prompt_template)
			]
		)

		# Format the documents into a string for the prompt
		formatted_document = ''
		for idx, doc in enumerate(documents):
			metadata = getattr(doc, 'metadata', {})
			text = doc.page_content
			is_table = metadata.get('type', None) == 'table'
			if not is_table:
				formatted_document += (
					f"- Text Document {idx + 1}: \n```"
					f"\nData context: {metadata['topic']}"
					f"\nData:\n{text}\n"
					f"```\n\n"
				)
			else:
				formatted_document += (
					f"- Table Document as csv string {idx + 1}: \n```"
					f"\nData context: {metadata['topic']}"
					f"\nTable data:\n{text}\n"
					f"```\n\n"
				)

		chain = prompt | llm
		responses = chain.invoke({"question": question, "documents": formatted_document})

		return responses.binary_scores


if __name__ == '__main__':
	question = "What are the benefits of Self-RAG?"
	context = "Self-RAG enhances retrieval accuracy by allowing self-assessment of generated responses."
	documents = [Document(page_content=context, metadata={})]
	response = GradeDocumentsService.grade_documents(question, documents)
	print(response)
