from typing import Union

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.services.custom_llm.services.llm_utils import LLMUtils
from src.services.rag_services.models.doc_processor_element import DocProcessorElement


class HandleTextLLMService:
	@staticmethod
	def summary_text(texts: list[str]):
		# Define the prompt
		prompt_text = """You are an assistant tasked with summarizing tables and text. \
		Give a concise summary of the table or text. Table or text chunk: {element} """
		text_summaries = HandleTextLLMService.__run_task(prompt_text, texts)

		return text_summaries

	@staticmethod
	def __run_task(prompt_text, texts, max_concurrency=5, configs=None):
		if configs is None:
			configs = {}

		# Create the chain
		prompt = ChatPromptTemplate.from_template(prompt_text)
		llm = LLMUtils.get_azure_openai_llm()
		summarize_chain = {"element": lambda x: x} | prompt | llm | StrOutputParser()

		# Start running the task
		response = summarize_chain.batch(texts, {"max_concurrency": max_concurrency} | configs)

		return response

	@classmethod
	def extract_text(cls, texts: list[Union[DocProcessorElement, str]]):
		return [
			i.text if isinstance(i, DocProcessorElement) else i for i in texts
		]
