from typing import Union

from src.services.custom_llm.services.handle_text_llm_service import HandleTextLLMService
from src.services.rag_services.models.doc_processor_element import DocProcessorElement


class HandelTextLLMController:
	@staticmethod
	def summary_text(texts: list[Union[DocProcessorElement, str]], tables: list[Union[DocProcessorElement, str]]):
		texts_str = HandleTextLLMService.extract_text(texts)
		tables_str = HandleTextLLMService.extract_text(tables)

		# Get the summaries
		text_summaries = HandleTextLLMService.summary_text(texts_str)
		table_summaries = HandleTextLLMService.summary_text(tables_str)

		return text_summaries, table_summaries
