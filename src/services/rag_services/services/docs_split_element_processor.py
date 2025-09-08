import asyncio
import logging
import os
import re
import tempfile
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path

import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter
from unstructured.documents.elements import Element, Table, Text, Title
from unstructured.partition.docx import partition_docx
from unstructured.partition.md import partition_md

from src.constants.rag_company_constant import special_separators
from src.services.rag_services.models.docs_split_elements_models.doc_element_type import (
    DocElementTypeEnum,
)
from src.services.rag_services.models.docs_split_elements_models.group_doc_element import (
    GroupDocsElement,
)
from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.services.rag_services.services.process_image_in_file import ProcessImage

_logger = logging.getLogger("DocsSplitElementsProcessor")


class DocsSplitElementsProcessor:
    """Processor for splitting elements from a document."""

    def __init__(self, doc_retriever: DocumentRetriever) -> None:
        """Initialize the processor."""
        self.doc_retriever = doc_retriever
        self.split_text = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=100,
            separators=[
                "\n\n",
                "\n",
                r"(?<=\. )",
                " ",
                ",",
                *special_separators,
                "",
            ],
        )

    async def process_single_doc(
        self, file_path: str, topic_name: str | None = None, view_url: str | None = None
    ) -> None:
        """Process a single document."""
        filename = Path(file_path).stem
        file_extension = Path(file_path).suffix
        topic_name = topic_name or filename

        _logger.info("---- Processing file: %s", topic_name)

        text_elements, table_elements, image_elements, image_data = await self._process_file_with_extension(
            file_path, file_extension
        )
        # Export elements
        texts = [element.export() for element in text_elements]
        tables = [element.export() for element in table_elements]
        images = [element.export(image_collection=image_data) for element in image_elements]
        # Add documents to the in-memory store
        await self.doc_retriever.add_documents(texts, filename, "text", topic_name, view_url)
        await self.doc_retriever.add_documents(tables, filename, "table", topic_name, view_url)
        await self.doc_retriever.add_documents(images, filename, "image", topic_name, view_url)

    async def _process_file_with_extension(
        self,
        file_path: str,
        file_extension: str,
    ) -> tuple[list[GroupDocsElement], list[GroupDocsElement], list[GroupDocsElement], dict]:
        """Process a DOCX file and extract its content elements.

        Args:
            file_path (str): Path to the DOCX file to be processed

        Returns:
            tuple[list[GroupDocsElement], list[GroupDocsElement], list[GroupDocsElement], dict]:
                - list[GroupDocsElement]: Non-table elements (text content)
                - list[GroupDocsElement]: Table elements
                - list[GroupDocsElement]: Image elements
                - dict: Collection of processed images in base64 format

        """
        _logger.info("---- Processing file: %s", file_path)
        with tempfile.TemporaryDirectory() as destination_dir:
            # Ensure the destination directory exists
            Path(destination_dir).mkdir(parents=True, exist_ok=True)
            # Set the destination file name to be in the local project directory
            file_name = Path(file_path).name
            destination_file_name = Path(destination_dir) / file_name

            if self.doc_retriever.collection_name == "wms":
                file_path, image_collection = ProcessImage().convert_docx_images_to_base64(
                    file_path,
                    str(destination_file_name),
                    is_process_summary=False,
                )
            else:
                image_collection = {}
            # Extract elements from the DOCX file
            if file_extension == ".docx":
                partition_handler = partition_docx
            elif file_extension == ".md":
                partition_handler = partition_md
            else:
                raise NotImplementedError(f"File extension {file_extension} is not supported")

            def run_partition_sync(file_path: str) -> list[Element]:
                try:
                    return partition_handler(
                        filename=file_path,
                        infer_table_structure=True,
                        strategy="hi_res",
                        chunking_strategy="by_title",
                        max_characters=50000,
                        new_after_n_chars=48000,
                        combine_text_under_n_chars=2000,
                    )
                except Exception as e:
                    _logger.error("Failed to process %s: %s", file_path, e)
                    msg = f"Document processing failed for {file_path}"
                    raise RuntimeError(msg) from e

            with ThreadPoolExecutor(max_workers=1) as executor:
                raw_elements = await asyncio.get_event_loop().run_in_executor(executor, run_partition_sync, file_path)
            all_elements = self.extract_elements(raw_elements)

            # Group elements by heading (title)
            grouped_elements = self.group_elements(all_elements)

            # Extract table with title in each group
            tables, non_tables, image_groups = self.extract_tables_notables(grouped_elements)

            # Combine small text groups, split large text groups
            non_tables = self.combine_or_split_text_groups(non_tables)

            _logger.info(f"Images: {[group.shape for group in image_groups]}")

            return non_tables, tables, image_groups, image_collection

    @staticmethod
    def extract_elements(raw_elements: list[Element]) -> list[Element]:
        """Extract original elements from the raw elements list.

        The raw elements list contains elements that were implemented the default partitioning strategy
        of the unstructured library, which can give unexpected results.
        This method extracts the original elements from the raw elements before the package processing them further.

        Args:
            raw_elements (list[Element]): List of raw elements extracted from the document.

        Returns:
            list[Element]: List of original elements, which can be text, table, title and other elements (which will be as
                        text elements).

        """
        all_original_elements: OrderedDict[str, Element] = OrderedDict()

        for element in raw_elements:
            for ori_element in getattr(element.metadata, "orig_elements", []):
                if ori_element.id not in all_original_elements and (
                    ori_element.text or ori_element.metadata.text_as_html
                ):
                    all_original_elements[ori_element.id] = ori_element

        return list(all_original_elements.values())

    @staticmethod
    def group_elements(all_elements: list[Element]) -> list[list[Element]]:
        """Group elements by their titles. Titles are used to create hierarchical groups of elements.

        Args:
            all_elements (list[Element]): List of elements to be grouped.

        Returns:
            list[list[Element]]: List of grouped elements, where each group is a list of elements.

        """
        grouped: list[list[Element]] = []

        def wrap_title(index: int, titles: list[Element] | None = None) -> int:
            """Recursively wraps titles and groups elements under their respective titles.

            Args:
                    index (int): Current index in the all_elements list.
                    titles (list[Title], optional): List of titles to be used for grouping.

            Returns:
                    int: The next index to be processed.

            """
            if index >= len(all_elements):
                return index
            if titles is None:
                titles = []
            if isinstance(all_elements[index], Title):
                new_title_level = all_elements[index].metadata.category_depth
                if not titles or new_title_level < titles[-1].metadata.category_depth:
                    return_index = wrap_title(index + 1, [all_elements[index]])
                else:
                    while titles and titles[-1].metadata.category_depth == new_title_level:
                        titles = titles[:-1]
                    return_index = wrap_title(index + 1, titles + [all_elements[index]])
                if return_index < len(all_elements):
                    return wrap_title(return_index, titles)
                return return_index

            non_titles = []
            while index < len(all_elements) and not isinstance(all_elements[index], Title):
                non_titles.append(all_elements[index])
                index += 1
            new_group = [*titles, *non_titles]
            if new_group:
                grouped.append(new_group)

            return index

        start_index = 0
        while start_index < len(all_elements):
            start_index = wrap_title(start_index)
            if start_index >= len(all_elements):
                break

        return grouped

    @staticmethod
    def extract_tables_notables(grouped_elements):
        """Extract tables and non-table elements from grouped elements.

        Args:
                grouped_elements (list): List of grouped elements, where each group is a list of elements.

        Returns:
                tuple: A tuple containing two lists - table groups and non-table groups.

        """

        # Type checking for table, image, text
        def get_element_type(element):
            pattern = r"<base64>.*?</base64>"
            if isinstance(element, Table) and element.metadata.text_as_html:
                # Confirm it's not an empty table by checking DataFrame
                try:
                    df = pd.concat(
                        pd.read_html(StringIO(element.metadata.text_as_html), header=0),
                        ignore_index=True,
                    )
                except Exception as e:
                    _logger.error(f"Error parsing table: {e}. Keep as text")
                    df = pd.DataFrame()
                if not df.empty:
                    return DocElementTypeEnum.TABLE
            # Check if the element is an image
            if re.search(pattern, element.text):
                return DocElementTypeEnum.IMAGE
            # Everything else with text is treated as text
            if element.text:
                return DocElementTypeEnum.TEXT
            return None

        table_groups = []
        not_table_groups = []
        image_groups = []
        for group in grouped_elements:
            # Determine element types once for each item
            typed_items = [(item, get_element_type(item)) for item in group]

            # Titles
            titles = [item for (item, etype) in typed_items if isinstance(item, Title) and item.text]

            # Slices by type
            table_group = [item for (item, etype) in typed_items if etype == DocElementTypeEnum.TABLE]
            text_group = [
                item
                for (item, etype) in typed_items
                if etype == DocElementTypeEnum.TEXT and not isinstance(item, Title) and item.text
            ]
            image_group = [item for (item, etype) in typed_items if etype == DocElementTypeEnum.IMAGE]

            # Build result objects
            if image_group:
                image_groups.append(GroupDocsElement(titles, image_group, DocElementTypeEnum.IMAGE))
            if table_group:
                table_groups.append(GroupDocsElement(titles, table_group, DocElementTypeEnum.TABLE))
            if text_group:
                not_table_groups.append(GroupDocsElement(titles, text_group, DocElementTypeEnum.TEXT))

        return table_groups, not_table_groups, image_groups

    def combine_or_split_text_groups(self, non_tables):
        """Combine or split text groups based on their character length.

        - Combines small groups into one group
        - Splits large groups into multiple groups

        Args:
                non_tables (list[GroupDocsElement]): List of non-table elements to be processed.

        Returns:
                list[GroupDocsElement]: List of combined or split text groups.

        """
        new_groups = []
        index = 0
        max_chars = 2000
        max_over_accepted_chars = 3000

        while index < len(non_tables):
            current_shape = non_tables[index].shape
            if max_chars <= current_shape <= max_over_accepted_chars:
                new_groups.append(non_tables[index])
                index += 1
            elif current_shape < max_chars:
                next_idx = index + 1
                new_shape = current_shape
                combined_group = non_tables[index]
                while next_idx < len(non_tables):
                    new_shape += non_tables[next_idx].shape
                    if new_shape > max_over_accepted_chars:
                        break
                    # Update combined_group and its metadata
                    combined_group = GroupDocsElement.combine(combined_group, non_tables[next_idx])
                    next_idx += 1
                    if new_shape > max_chars:
                        break

                new_groups.append(combined_group)
                index = next_idx
            else:
                split_docs = self.split_text.split_text(str(non_tables[index]))
                metadata = non_tables[index].metadata
                new_groups.extend(
                    [GroupDocsElement([], [Text(doc)], DocElementTypeEnum.TEXT, metadata) for doc in split_docs]
                )
                index += 1

        return new_groups
