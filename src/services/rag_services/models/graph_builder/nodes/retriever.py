import io
import logging
import re
import traceback
from collections import defaultdict
from math import ceil

import pandas as pd
from langchain.output_parsers import BooleanOutputParser
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.document_compressors import LLMChainFilter
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from sqlalchemy import select

from src.constants.llm_constant import AZURE_LLM00
from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.services.rag_services.models.graph_builder.prompts import RERANKER_PROMPT

logger = logging.getLogger(__name__)


async def retrieve_unique_docs_by_hybrid_search(
    queries: list[str],
    doc_retriever: DocumentRetriever,
):
    """Retrieve unique documents based on multiple queries using an EnsembleRetriever.

    This function performs a hybrid search by combining results from a vector-based retriever
    and a BM25 retriever. It ensures that the retrieved documents are unique and returns
    a capped number of results.

    Args:
            queries (list[str]): A list of search queries to execute.
            doc_retriever (DocumentRetriever): The document retriever instance used for fetching documents.

    Returns:
            list[dict]: A list of unique document dictionaries containing content, metadata, and other details.

    """
    max_return_docs = 30
    number_of_docs = ceil(
        max_return_docs / len(queries),
    )  # Calculate the number of documents per query
    number_of_docs = max(number_of_docs, 4)

    # Set up BM25 retriever with the same documents
    bm25_retriever = await create_bm25_retriever(doc_retriever, number_of_docs)
    if bm25_retriever is None:
        return []

    # Set up vector retriever
    vector_retriever = doc_retriever.vector_store.as_retriever(
        search_kwargs={"k": number_of_docs},
    )

    # Define weights for the ensemble retriever
    vector_percent = 0.8
    bm25_percent = 0.2

    # Create an ensemble retriever with custom weights
    ensemble_retriever = EnsembleRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        weights=[vector_percent, bm25_percent],  # 80% weight to vector, 20% to BM25
    )

    all_results = []
    queries = [query for query in queries if query]  # Filter out empty queries

    # Run all queries concurrently using the ensemble retriever
    retrieved_docs = await ensemble_retriever.abatch(queries)
    retrieved_docs_flattened = [doc for docs in retrieved_docs for doc in docs]

    unique_ids = set()
    for doc in retrieved_docs_flattened:
        if doc.id not in unique_ids:
            doc.metadata["collection_name"] = (
                f"Your Collection: {doc_retriever.collection_base_name}"
                if doc_retriever.is_user_collection
                else doc_retriever.collection_name
            )
            result = {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "id": doc.id,
                "retrieval_method": "ensemble",
            }
            all_results.append(result)
            unique_ids.add(doc.id)

    return all_results[:max_return_docs]


async def create_bm25_retriever(doc_retriever: DocumentRetriever, number_of_docs: int):
    """Creates a BM25 retriever using documents from the vector store.

    This function retrieves documents from the vector store associated with the
    provided `doc_retriever`, converts them into LangChain `Document` objects,
    and initializes a BM25 retriever with the specified number of documents.

    Args:
            doc_retriever (DocumentRetriever): The document retriever instance containing
                    the vector store and collection information.
            number_of_docs (int): The number of documents to retrieve for the BM25 retriever.

    Returns:
            BM25Retriever: An instance of BM25Retriever initialized with the retrieved documents.
            None: If no documents are found in the vector store.

    """
    async with doc_retriever.vector_store.session_maker() as session:
        # First get the collection ID
        collection = await doc_retriever.vector_store.aget_collection(session)
        collection_id = collection.uuid
        # Then query the embedding store table directly
        embedding_table = doc_retriever.vector_store.EmbeddingStore
        statement = select(embedding_table).where(
            embedding_table.collection_id == collection_id,
        )
        db_collection = await session.execute(statement)

    if not db_collection:
        return None

    # Fix: Correctly access the attributes from the EmbeddingStore object
    langchain_docs = [
        Document(
            page_content=row.EmbeddingStore.document,
            metadata=row.EmbeddingStore.cmetadata or {},
            id=row.EmbeddingStore.id,
        )
        for row in db_collection
    ]
    if len(langchain_docs) == 0:
        return None
    bm25_retriever = BM25Retriever.from_documents(langchain_docs, k=number_of_docs)

    return bm25_retriever


def fusion_docs(docs: list[dict]):
    """Groups and fuses documents based on their metadata.

    This function groups documents by their `document_name` metadata, combines their content,
    and creates a new document for each group. The resulting documents are sorted by their
    `order_number` metadata.

    Args:
            docs (list[dict]): A list of document dictionaries, where each dictionary contains
                    'content' and 'metadata' keys.

    Returns:
            tuple: A tuple containing fused documents and a dictionary of grouped documents.

    """
    group_ = defaultdict(list)

    for doc in docs:
        group_[doc["metadata"]["document_name"]].append(doc)

    fusion_docs_ = []
    for doc_name, arrays in group_.items():
        titles = ", ".join(set(doc["metadata"]["titles"] for doc in arrays))
        topic = arrays[0]["metadata"]["topic"]
        view_url = arrays[0]["metadata"]["view_url"]
        document_collection = arrays[0]["metadata"]["document_collection"]
        order_number = min(doc["metadata"]["order"] for doc in arrays)
        contents = [doc["content"] for doc in arrays if doc["content"]]
        new_doc = dict(
            content=topic + "\n" + titles + "\n\n" + "\n\n".join(contents),
            metadata=dict(
                topic=topic,
                titles=titles,
                view_url=view_url,
                order_number=order_number,
                document_collection=document_collection,
            ),
        )
        fusion_docs_.append(new_doc)

    # sort by order_number
    fusion_docs_ = sorted(fusion_docs_, key=lambda x: x["metadata"]["order_number"])

    return fusion_docs_, group_


def dataframe_to_xml(df, root_name="root", row_name="row"):
    """Converts a pandas DataFrame into an XML string.

    Args:
            df (pandas.DataFrame): The DataFrame to convert.
            root_name (str): The name of the root XML element. Defaults to "root".
            row_name (str): The name of the XML element for each row. Defaults to "row".

    Returns:
            str: An XML string representation of the DataFrame.

    """

    def simple_sanitize_xml_tag(name):
        """Sanitizes a string to make it a valid XML tag.

        Args:
                name (str): The string to sanitize.

        Returns:
                str: A sanitized string that can be used as an XML tag.

        """
        sanitized = re.sub(r"[\s<>&\'\"]+", "_", str(name))
        if sanitized and (not sanitized[0].isalpha() and sanitized[0] != "_"):
            sanitized = "col_" + sanitized
        return sanitized

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', f"<{root_name}>"]
    column_map = {col: simple_sanitize_xml_tag(col) for col in df.columns}

    for idx, row in df.iterrows():
        xml_parts.append(f"  <{row_name}>")
        for col, value in row.items():
            if pd.isna(value):
                xml_parts.append(f'    <{column_map[col]} xsi:nil="true"/>')
            else:
                escaped_value = re.escape(str(value))
                xml_parts.append(
                    f"    <{column_map[col]}>{escaped_value}</{column_map[col]}>",
                )
        xml_parts.append(f"  </{row_name}>")

    xml_parts.append(f"</{root_name}>")

    return "\n".join(xml_parts)


def reformat_docs(docs: list[dict]):
    """Reformats a list of documents and extracts tables.

    This function processes a list of document dictionaries, extracting metadata
    and content, and reformats them into a standardized structure. If a document
    contains a table, it attempts to parse the table data into a pandas DataFrame
    and converts it to XML format. Extracted tables are stored separately.

    Args:
            docs (list[dict]): A list of document dictionaries, where each dictionary
                    contains 'content' and 'metadata' keys.

    Returns:
            tuple: A tuple containing:
                    - reformat_docs (list[dict]): A list of reformatted document dictionaries.
                    - tables (list[pandas.DataFrame]): A list of extracted tables as pandas DataFrames.

    """
    reformat_docs = []
    tables = []

    for doc in docs:
        metadata_ = doc["metadata"]
        topic = metadata_["topic"]
        view_url = metadata_.get("view_url")
        title = metadata_["titles"]
        type_ = metadata_["type"]
        order_number = metadata_["order"]
        content = doc["content"]
        document_name = metadata_["document_name"]
        document_collection = metadata_.get("collection_name", None)
        if type_ == "table":
            table_data = metadata_.get("table", content)
            if not table_data:
                logger.warning(
                    f"_type is table but no table data found for {document_collection} {document_name} document_id: {doc['id']} ",
                )
            else:
                try:
                    table_df = pd.read_csv(io.StringIO(table_data), delimiter=";")
                    if table_df.empty:
                        logger.warning(
                            f"Table data is empty for {document_collection} {document_name} document_id: {doc['id']} ",
                        )
                    else:
                        table_df.attrs["topic"] = topic
                        tables.append(table_df)
                        content = dataframe_to_xml(table_df)
                        content = topic + "\n" + title + "\n\n" + content
                except Exception:
                    logger.error(
                        f"Error pandas parse table data for {document_collection} {document_name} document_id: {doc['id']} ",
                    )

        new_doc = dict(
            content=content,
            metadata=dict(
                topic=topic,
                titles=title,
                view_url=view_url,
                type=type_,
                document_name=document_name,
                order=order_number,
                document_collection=document_collection,
            ),
        )
        reformat_docs.append(new_doc)

    return reformat_docs, tables


def reformat_and_fusion_docs(retrieved_docs):
    """Reformats and fuses retrieved documents.

    This function assigns an order to each document, reformats the documents,
    and then fuses them based on their metadata. The result is a list of
    reformatted and fused documents, along with any extracted tables.

    Args:
            retrieved_docs (list[dict]): A list of retrieved document dictionaries
                    with content and metadata.

    Returns:
            tuple: A tuple containing:
                    - retrieved_docs (list[dict]): A list of reformatted and fused document dictionaries.
                    - tables (list[pandas.DataFrame]): A list of tables extracted from the documents.

    """
    for idx in range(len(retrieved_docs)):
        retrieved_docs[idx]["metadata"]["order"] = idx
    retrieved_docs, tables = reformat_docs(retrieved_docs)
    retrieved_docs, _ = fusion_docs(retrieved_docs)
    return retrieved_docs, tables


async def filter_in_relevant_documents(
    user_question,
    gen_queries,
    retrieved_docs,
    tables,
):
    """Filters and reranks retrieved documents and tables based on relevance to the user's question and generated queries.

    Args:
            user_question (str): The original question or message from the user.
            gen_queries (list[str]): A list of generated queries related to the user's question.
            retrieved_docs (list[dict]): A list of retrieved document dictionaries with content and metadata.
            tables (list[pandas.DataFrame]): A list of tables extracted from the retrieved documents.

    Returns:
            tuple: A tuple containing:
                    - filtered_docs (list[dict]): A list of filtered and reranked document dictionaries.
                    - tables (list[pd.DataFrame]): A list of filtered tables relevant to the user's question.

    """
    try:
        # Map documents by their topic for quick access
        mapped_docs = {doc["metadata"]["topic"]: doc for doc in retrieved_docs}

        # Combine user question and generated queries into a single string
        questions = "\n".join(map(lambda x: "- " + x, {user_question, *gen_queries}))

        # Convert retrieved documents into a format suitable for filtering
        temp_docs = [
            Document(
                page_content=(f"Topic: {doc['metadata']['topic']}\n{doc['content']}"),
                metadata=doc["metadata"],
            )
            for doc in retrieved_docs
        ]

        # Create a prompt template for filtering documents
        prompt = PromptTemplate(
            template=RERANKER_PROMPT,
            input_variables=["question", "context"],
            output_parser=BooleanOutputParser(),
        )

        # Apply the LLM-based filter to compress documents based on relevance
        _filter = LLMChainFilter.from_llm(llm=AZURE_LLM00, prompt=prompt)
        filter_temp_docs = await _filter.acompress_documents(temp_docs, questions)

        # Extract topics of filtered documents
        mapped_filter_docs = {doc.metadata["topic"] for doc in filter_temp_docs}

        # Filter documents and tables based on the topics of filtered documents
        filtered_docs = [mapped_docs[topic] for topic in mapped_filter_docs]
        tables = [
            table for table in tables if (topic := table.attrs.get("topic", None)) and topic in mapped_filter_docs
        ]

        return filtered_docs, tables
    except Exception as e:
        # Log any errors encountered during filtering
        logger.error(f"Error when filtering in relevant docs: {e}")

    # Return the original documents and tables if an error occurs
    return retrieved_docs, tables


async def retriever(human_message, english_queries, analyze_mode, doc_retriever):
    """Retrieve relevant documents based on English search queries and the original user question.

    Args:
            human_message (str): The original user question or message.
            english_queries (list[str]): A list of English search queries to execute.
            analyze_mode (bool): Whether to apply additional filtering and reranking of documents.
            doc_retriever (DocumentRetriever): The document retriever instance used for fetching documents.

    Returns:
        tuple: A tuple containing:
            - retrieved_docs (list[dict]): A list of retrieved document dictionaries with content and metadata.
            - tables (list[pd.DataFrame]): A list of tables extracted from the retrieved documents.

    """
    retrieved_docs = []
    tables = []
    if not english_queries:
        return [], []
    try:
        # Use hybrid search instead of vector-only search
        retrieved_docs: list[dict] = await retrieve_unique_docs_by_hybrid_search(
            english_queries,
            doc_retriever,
        )
        retrieved_docs, tables = reformat_and_fusion_docs(retrieved_docs)
    except Exception as e:
        logger.error(
            f"Error retrieving documents: {e}. Traceback: {traceback.format_exc()}",
        )

    # Apply reranker if analyze mode is on
    if analyze_mode is True:
        retrieved_docs, tables = await filter_in_relevant_documents(
            human_message,
            english_queries,
            retrieved_docs,
            tables,
        )

    return retrieved_docs, tables
