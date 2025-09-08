from typing import Union
from langchain_core.documents import Document
from src.services.custom_llm.services.grade_documents_service import GradeDocumentsService


class GradeDocumentsController:
	@staticmethod
	def filter_relevant_documents(question, documents: list[Union[Document, dict]]):
		if not documents:
			return []
		if isinstance(documents[0], dict):
			processed_docs = []
			for doc in documents:
				
				doc = Document(page_content=doc.get('content'), metadata=doc.get('metadata'))
				processed_docs.append(doc)
				processed_docs[-1].metadata["base64"] = None
		else:
			processed_docs = documents
		binary_scores = GradeDocumentsService.grade_documents(question, processed_docs)

		return [doc for doc, score in zip(documents, binary_scores) if score == 1]
