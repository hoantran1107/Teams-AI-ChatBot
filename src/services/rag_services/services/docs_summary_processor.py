import os
import logging
from unstructured.partition.docx import partition_docx
from src.services.custom_llm.controllers.handle_text_llm_controller import HandelTextLLMController
from src.services.rag_services.models.doc_processor_element import DocProcessorElement
from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.utils.file_helper import get_creation_time, get_file_name, get_modification_time

# Configure logger
logger = logging.getLogger(__name__)

class DocsSummaryProcessor:
	"""
	class responsible for processing DOCX (only acceptable doc for now) documents and managing their storage.

	This class provides functionality for traversing a directory structure, extracting content
	from DOCX files, summarizing the text and table data within these documents, and populating
	an in-memory retrieval mechanism for managing these processed documents.

	Attributes:
		combine_text_under_n_chars (int): The threshold (in characters) to combine smaller
			text blocks during document processing.
		new_after_n_chars (int): The limit (in characters) after which a new processing chunk
			is created within a document.
		max_chars (int): The upper limit (in characters) for processing content from a
			document chunk.
		doc_retriever (DocumentRetriever): The retrieval mechanism to manage processed
			documents in memory.
		root_path (str): The root directory path containing the documents to be processed.

	Methods:
		prepare_docs:
			Processes and summarize all documents from the specified directory and store
			them into the in-memory document retrieval system.
	"""

	def __init__(
			self, root_path: str, doc_retriever: DocumentRetriever, max_chars: int = 4000,
			new_after_n_chars: int = 3800, combine_text_under_n_chars: int = 2000
	):
		super().__init__()
		self.combine_text_under_n_chars = combine_text_under_n_chars
		self.new_after_n_chars = new_after_n_chars
		self.max_chars = max_chars
		self.doc_retriever = doc_retriever
		self.root_path = root_path

	def prepare_docs(self):
		# Get data for all documents in the directory and subdirectories
		all_documents = self.__process_files()

		for file_path, (text_elements, table_elements) in all_documents.items():
			text_summaries, table_summaries = HandelTextLLMController.summary_text(text_elements, table_elements)

			# Add documents to the in-memory store
			self.doc_retriever.add_summary_documents(
				text_elements, text_summaries,
				table_elements, table_summaries,
			)

		logger.info("Documents processed and stored successfully")

	def __process_files(self):
		all_docs = {}
		# Traverse the root path and process all DOCX files in the directory and subdirectories
		for dir_path, _, filenames in os.walk(self.root_path):
			for filename in filenames:
				if filename.endswith(".docx"):  # Process only DOCX files
					file_path = os.path.join(dir_path, filename)
					try:
						all_docs[filename] = self.__process_docx(file_path)
						logger.info(f"DocsProcessor processed file: {filename}")
					except Exception as e:
						logger.error(f"DocsProcessor failed to process {filename}: {e}")

		return all_docs

	def __process_docx(self, file_path):
		raw_elements = partition_docx(
			filename=file_path,
			partition_by_api=False,
			extract_images_in_pdf=False,
			infer_table_structure=True,
			strategy="hi_res",
			chunking_strategy="by_title",
			max_characters=self.max_chars,
			new_after_n_chars=self.new_after_n_chars,
			combine_text_under_n_chars=self.combine_text_under_n_chars,
			image_output_dir_path=self.root_path,
		)

		# Extract file metadata
		file_metadata = {
			"file_name": get_file_name(file_path),
			"creation_time": get_creation_time(file_path),
			"modification_time": get_modification_time(file_path),
		}

		# Categorize elements into tables and text
		table_elements = []
		text_elements = []
		for element in raw_elements:
			if "unstructured.documents.elements.Table" in str(type(element)):
				table_elements.append(
					DocProcessorElement(type="table", text=str(element.metadata.text_as_html), metadata=file_metadata)
				)
			elif "unstructured.documents.elements.CompositeElement" in str(type(element)):
				text_elements.append(
					DocProcessorElement(type="text", text=str(element), metadata=file_metadata)
				)

		return text_elements, table_elements
