import asyncio
import logging
import os

import openai

from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service
from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.services.rag_services.services.docs_split_element_processor import DocsSplitElementsProcessor

_logger = logging.getLogger("RagVectorStoreService")


class RagStoreService:
    """Service class to manage RAG vector store operations."""

    def __init__(self, doc_retriever: DocumentRetriever):
        self.doc_retriever = doc_retriever

    async def add_documents_to_vector_store(
        self, file_name: str, topic_name: str | None = None, view_url: str | None = None
    ) -> tuple[bool, str | None]:
        """Add a document to the vector store and log it.

        This method processes a document, splits it into elements, and adds them to the vector store.
        It includes retry logic for handling rate limit errors from OpenAI.
        After successful processing, it removes the local file.

        Args:
            file_name (str): Path to the local file to be processed and added to the vector store.
            topic_name (str, optional): A descriptive name for the document that is easier to understand.
                Defaults to None.
            view_url (str, optional): URL where the document can be viewed. Defaults to None.

        Returns:
            tuple: A tuple containing:
                - bool: True if the document was successfully added, False otherwise.
                - str or None: Error message if an error occurred, None otherwise.

        """
        retries = 1
        delay = 6
        error = None
        for attempt in range(retries):
            try:
                link_to_local_file = file_name
                docs_split_elements_processor = DocsSplitElementsProcessor(self.doc_retriever)
                await docs_split_elements_processor.process_single_doc(
                    link_to_local_file, topic_name=topic_name, view_url=view_url
                )
                os.remove(link_to_local_file)
                return True, error
            except openai.RateLimitError as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    error = f"Rate limit exceeded for {file_name}: {str(e)}"
                    _logger.error(error)
                    return False, error
            except Exception as e:
                _logger.error(f"Add failed for {file_name}: {str(e)}", exc_info=True)
                return False, error

        return False, error

    async def delete_document_with_doc_prefix(self, doc_id_prefixes):
        """Delete documents from vector store by prefix"""
        return await self.doc_retriever.remove_documents(doc_id_prefixes)

    async def update_rag_vector_store(
        self,
        doc_id_prefixes,
        link_to_gcp_bucket,
        gcp_path_document,
        already_downloaded: bool = False,
        topic_name: str | None = None,
    ):
        """Update vector store with new document content"""
        try:
            await self.doc_retriever.remove_documents(doc_id_prefixes)
            if not already_downloaded:
                link_to_local_file = gcp_bucket_service.download_file_from_gcp_bucket(
                    link_to_gcp_bucket, gcp_path_document
                )
            else:
                link_to_local_file = link_to_gcp_bucket
            if not link_to_local_file:
                return False
            docs_split_elements_processor = DocsSplitElementsProcessor(self.doc_retriever)
            await docs_split_elements_processor.process_single_doc(link_to_local_file, topic_name)
            os.remove(link_to_local_file)
            return True
        except Exception as e:
            _logger.error(f"Update RAG vector store failed: {str(e)}")
            return False
