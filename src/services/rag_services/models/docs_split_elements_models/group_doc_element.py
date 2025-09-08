import logging
import re
from io import StringIO

import pandas as pd
from unstructured.documents.elements import Table, Title

from src.constants.rag_company_constant import special_separators
from src.services.custom_llm.services.proccess_images import summary_image_using_llm
from src.services.rag_services.models.doc_processor_element import DocProcessorElement
from src.services.rag_services.models.docs_split_elements_models.doc_element_type import DocElementTypeEnum

_logger = logging.getLogger(__name__)


class GroupDocsElement:
    """GroupDocsElement is a class that represents a group of documents."""

    def __init__(self, titles: list[Title], elements: list, item_type: DocElementTypeEnum, input_metadata=None):
        self.__input_metadata = input_metadata if input_metadata else dict()
        self.titles = titles
        self.elements = elements
        self.item_type = item_type

    @property
    def metadata(self):
        """Provides metadata information by combining default metadata with input metadata.

        Default metadata includes
        information derived from the object's titles and the filename of its first element. Additional input metadata
        is merged cautiously, with specific handling for 'titles' to avoid duplicates.

        Returns:
                dict: The resulting metadata dictionary containing processed 'titles', 'topic' derived from the
                                filename of the first element, and other properties merged from the input metadata.

        """
        default_metadata = {
            "titles": [t.text for t in self.titles],
            "topic": self.elements[0].metadata.filename,
            "type": self.item_type.value,
        }
        for key, value in self.__input_metadata.items():
            if key not in default_metadata:
                default_metadata[key] = value
            else:
                if key == "titles":
                    new_titles = default_metadata[key]
                    for title in value:
                        if title not in default_metadata[key]:
                            default_metadata[key].append(title)
                    default_metadata[key] = new_titles
                else:
                    default_metadata[key] = value

        # remove special separators from titles
        for i in range(len(default_metadata["titles"])):
            for separator in special_separators:
                default_metadata["titles"][i] = default_metadata["titles"][i].replace(separator, "")
        return default_metadata

    @property
    def shape(self) -> tuple[int, int] | int:
        """Determines the shape property value based on the item type.

        This property calculates and returns the shape for a table type item
        or calculates the sum of text lengths across elements for non-table
        item types.

        Returns:
                (tuple|int): If the item type is a table, returns the shape of the table data as
                                                a tuple (rows, columns). Otherwise, returns the total length of
                                                text across all elements as an integer.

        """
        if self.item_type == DocElementTypeEnum.TABLE:
            return self.__create_table_df().shape
        return sum([len(e.text) for e in self.elements])

    def __str__(self) -> str:
        """Representation of the GroupDocsElement as a string."""
        result = self.export(is_print=True)
        return str(result) if result is not None else ""

    def export(
        self,
        image_collection: dict | None = None,
        *,
        is_print: bool = False,
        export_table_as_df: bool = False,
    ):
        match self.item_type:
            case DocElementTypeEnum.TABLE:
                return self.__export_for_tables(export_table_as_df=export_table_as_df, is_print=is_print)
            case DocElementTypeEnum.IMAGE:
                return self.__export_for_images(image_collection, is_print)
            case _:
                return self.__export_for_texts(is_print)

    def __export_for_images(self, image_collection: dict | None, is_print: bool = False) -> DocProcessorElement | str:
        if image_collection is None:
            _logger.error("image_collection is required")
            return DocProcessorElement(type=self.item_type.value, text="", metadata=self.metadata)

        text_str = "\n".join([e.text for e in (self.titles + self.elements) if e.text])
        match = re.search(r"<base64>(.*?)</base64>", text_str)
        image_identifier = match.group(0) if match else None

        image_base_64 = image_collection.get(image_identifier)
        if image_base_64 is None:
            _logger.error("image_base_64 is not found in image_collection")
            return DocProcessorElement(type=self.item_type.value, text="", metadata=self.metadata)

        # Send image_base_64 to AI to summarize:
        _, summary_image = summary_image_using_llm(image_base_64, True)

        # Replace the matched string with the summary
        if image_identifier:
            summary_image_and_other_text = text_str.replace(image_identifier, summary_image)
        else:
            summary_image_and_other_text = text_str

        return (
            DocProcessorElement(
                type=self.item_type.value,
                text=summary_image_and_other_text,
                base64=image_base_64,
                metadata=self.metadata,
            )
            if not is_print
            else text_str
        )

    def __export_for_texts(self, is_print=False):
        text_str = "\n".join([e.text for e in (self.titles + self.elements) if e.text])

        return (
            DocProcessorElement(type=self.item_type.value, text=text_str, metadata=self.metadata)
            if not is_print
            else text_str
        )

    def __export_for_tables(self, *, export_table_as_df: bool, is_print: bool):
        """Export the table as a dataframe or a string."""
        df_combined = self.__create_table_df()

        if is_print:
            return df_combined.to_markdown(index=False)
        data = df_combined if export_table_as_df else df_combined.to_csv(index=False, sep=";")

        return DocProcessorElement(type=self.item_type.value, text=data, metadata=self.metadata)

    def __create_table_df(self) -> pd.DataFrame:
        tables = []
        for element in self.elements:
            if isinstance(element, Table):
                df = pd.read_html(StringIO(element.metadata.text_as_html), header=0)
                tables.extend(df)
        df_combined = pd.concat(tables, ignore_index=True)
        return df_combined  # type: ignore

    @staticmethod
    def combine(group1, group2):
        """
        Combines two GroupDocsElement objects into a single GroupDocsElement.

        This method merges the titles and elements of the two provided GroupDocsElement
        objects, ensuring that titles are not duplicated. The metadata of the resulting
        GroupDocsElement is also combined, with titles merged and the topic taken from
        the first group's metadata.

        Args:
                group1 (GroupDocsElement): The first GroupDocsElement to combine.
                group2 (GroupDocsElement): The second GroupDocsElement to combine.

        Returns:
                GroupDocsElement: A new GroupDocsElement containing the combined titles,
                elements, and metadata of the two input groups.
        """
        processed_titles = set()
        combined_elements = []

        for group in [group1, group2]:
            for element in [*group.titles, *group.elements]:
                if isinstance(element, Title) and element.id not in processed_titles:
                    processed_titles.add(element.id)
                    combined_elements.append(element)
                else:
                    combined_elements.append(element)

        metadata1 = group1.metadata
        metadata2 = group2.metadata
        combined_metadata = {
            "titles": metadata1["titles"] + [t for t in metadata2["titles"] if t not in metadata1["titles"]],
            "topic": metadata1["topic"],
        }

        return GroupDocsElement([], combined_elements, DocElementTypeEnum.TEXT, combined_metadata)
