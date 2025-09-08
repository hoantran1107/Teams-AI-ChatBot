import asyncio
import logging
import traceback

import yaml
from langchain_core.messages import HumanMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langgraph.graph import StateGraph
from langgraph.types import StreamWriter
from pydantic import BaseModel, Field

from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import Collection
from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.services.rag_services.models.graph_builder import GraphBuilder, GraphState
from src.services.rag_services.models.graph_builder.nodes.retriever import (
    filter_in_relevant_documents,
    reformat_and_fusion_docs,
    retrieve_unique_docs_by_hybrid_search,
)
from src.services.rag_services.services.multiple_rag_sources.models.create_queries import (
    QueriesCollection,
)
from src.services.rag_services.services.multiple_rag_sources.prompts import (
    CREATE_QUERIES_PROMPT,
)

# Configure logger
logger = logging.getLogger(__name__)


class RequestedSource(BaseModel):
    source_name: str = Field(..., description="The name of the requested source")
    user_id: str = Field(..., description="The ID of the user who requested this source")


class GraphMultiSourceState(GraphState):
    question: str
    analysis_results: str
    requested_sources: list[dict]
    gen_multi_queries: list


class GraphBuilderMultiRagSource(GraphBuilder):
    def __init__(self, is_using_generate_node: bool = True):
        super().__init__()
        self.doc_retriever = None
        self.all_retrievers = {}
        self._graph_builder = StateGraph(GraphMultiSourceState)
        if is_using_generate_node:
            self._define_nodes()
        else:
            self._define_nodes_without_generate()

    @staticmethod
    def _get_valid_collections(sources: list[dict]) -> list[Collection]:
        valid_collections = []
        for source in sources:
            user_id = source.get("user_id")
            source_name = source.get("source_name")

            query_params = {"name": source_name}
            if user_id:
                query_params["user_id"] = user_id
            else:
                query_params["user_id"] = None
            collections = Collection.find_by_filter(**query_params)
            collection = collections[0] if collections else None

            if not collection:
                logger.warning(
                    f"Collection not found for source: {source_name}" + (f" and user_id: {user_id}" if user_id else ""),
                )
                continue

            if collection.note is None:
                logger.warning(
                    f"Collection {collection.name} has no note" + (f" for user {user_id}" if user_id else ""),
                )
                continue

            valid_collections.append(collection)

        if not valid_collections:
            logger.warning("Can't find any collection with notes for these sources: %s", sources)
            return []

        if len(valid_collections) != len(sources):
            logger.info(
                f"Found {len(valid_collections)} valid collections out of {len(sources)} requested. Valid collections: {valid_collections}",
            )

        return valid_collections

    def _initialize_retrievers(self, collections_query):
        self.all_retrievers = {}
        logger.debug(f"valid_collections in _initialize_retrievers: {collections_query}")
        for collection in collections_query:
            self.all_retrievers[
                collection.name if collection.user_id is None else f"{collection.name}_{collection.user_id}"
            ] = DocumentRetriever.create_doc_retriever(
                collection.name if not collection.user_id else f"{collection.name}_{collection.user_id}",
                is_user_collection=True if collection.user_id is not None else False,
                collection_base_name=collection.name,
            )

    @staticmethod
    def _build_embedded_source_string(
        valid_collections: list[Collection],
    ) -> tuple[list[dict], dict, dict]:
        embedded_source_list = []
        # Create mapping from internal key to display name
        key_to_display_mapping = {}
        # Create reverse mapping from display name to internal key
        display_to_key_mapping = {}

        for collection in valid_collections:
            source_identifier = (
                f"{collection.name}_{collection.user_id}" if collection.user_id is not None else collection.name
            )

            display_name = collection.name
            embedded_source_list.append(
                {
                    "source_name": display_name,
                    "source_note": collection.note,
                },
            )

            key_to_display_mapping[source_identifier] = display_name
            display_to_key_mapping[display_name] = source_identifier
        return embedded_source_list, key_to_display_mapping, display_to_key_mapping

    def _process_llm_response(
        self,
        response,
        valid_collections,
        display_to_key_mapping,
    ):
        pick_source_dict = {}
        processed_queries = []

        for item in response.queries:
            internal_key = display_to_key_mapping.get(item.source_name, item.source_name)
            pick_source_dict[internal_key] = item.queries
            updated_item = item.copy(update={"source_name": internal_key})
            processed_queries.append(updated_item)

        if not pick_source_dict or not processed_queries:
            # Fallback to use the source_name from the valid_collections
            pick_source_dict = {item.name: item.user_id for item in valid_collections}
            logger.warning(
                "No source_name found in the LLM response, using the source_name from the valid_collections: %s",
                pick_source_dict,
            )

        return pick_source_dict, processed_queries

    async def create_queries(self, state: GraphMultiSourceState, writer: StreamWriter) -> dict:
        """Generate multi-source queries using LLM based on user state and requested sources."""
        if state["classification_message"] in ("feedback", "greeting"):
            return {}

        writer({"picked_sources": "Searching knowledge base..."})

        sources = state["requested_sources"]

        # Handle empty sources gracefully
        if not sources:
            logger.warning("No sources provided for RAG query, returning empty result")
            writer({"picked_sources": "No knowledge sources specified for this query."})
            return {"gen_multi_queries": []}

        human_message = self._get_latest_human_message(state["messages"])
        if not human_message:
            logger.warning("No human message found in state messages")

        valid_collections = self._get_valid_collections(sources)

        # Handle case where no valid collections found
        if not valid_collections:
            logger.warning("No valid collections found for sources: %s", sources)
            source_names = [str(source) for source in sources]  # Convert to strings safely
            writer({"picked_sources": f"No accessible knowledge sources found for: {', '.join(source_names)}"})
            return {"gen_multi_queries": []}

        embedded_source_list, key_to_display_mapping, display_to_key_mapping = self._build_embedded_source_string(
            valid_collections,
        )

        prompt = self._build_prompt()
        llm_chain = prompt | self.llm.with_structured_output(QueriesCollection)
        histories = self._get_histories(state, human_message)
        interaction_instructions = self._get_interaction_instructions(state)

        response = await llm_chain.ainvoke(
            {
                "chat_history": histories,
                "embedded_source_list": embedded_source_list,
                "interaction_instructions": interaction_instructions,
            },
        )

        pick_source_dict, processed_queries = self._process_llm_response(
            response,
            valid_collections,
            display_to_key_mapping,
        )
        self._write_picked_sources(writer, pick_source_dict, key_to_display_mapping)

        collections_query = self._filter_collections_for_query(valid_collections, pick_source_dict)
        self._initialize_retrievers(collections_query)

        return {"gen_multi_queries": processed_queries}

    # --- Helper methods ---

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate(
            [
                SystemMessagePromptTemplate.from_template(template=CREATE_QUERIES_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
            ],
        )

    def _get_histories(self, state: GraphMultiSourceState, human_message: str) -> list:
        number_of_histories = 10
        return state["history"][-number_of_histories:] + [HumanMessage(content=human_message)]

    def _get_interaction_instructions(self, state: GraphMultiSourceState) -> str:
        instructions = state.get("instructions", [])
        return next(
            (item["instructions"] for item in instructions if item["name"] == "interaction_instruction"),
            "",
        )

    def _write_picked_sources(self, writer: StreamWriter, pick_source_dict: dict, key_to_display_mapping: dict):
        # Use mapping to get clean display names
        display_dict = {}
        for source_key, queries in pick_source_dict.items():
            display_name = key_to_display_mapping.get(source_key, source_key)
            display_dict[display_name] = queries

        parsed_yaml_source = yaml.dump(
            display_dict,
            default_flow_style=False,
            allow_unicode=True,
        ).replace("\n", "\n\n")

        writer({"picked_sources": parsed_yaml_source})

    def _filter_collections_for_query(self, valid_collections: list, pick_source_dict: dict) -> list:
        collections_query = []
        for item in valid_collections:
            key_with_user = f"{item.name}_{item.user_id}"
            internal_key = key_with_user if item.user_id is not None else item.name

            if internal_key in pick_source_dict:
                collections_query.append(item)
        return collections_query

    async def _retrieve_by_hybrid_search(self, state: GraphMultiSourceState, writer: StreamWriter):
        """Retrieve relevant documents based on source-specific English search queries and the original user question."""
        filtered_docs = []
        tables = []
        source_queries = state.get("gen_multi_queries", [])
        user_question = state["question"]
        try:
            source_queries = [item for item in source_queries if item.queries]
            if not source_queries or not user_question:
                return {"documents": [], "tables": []}

            # Limit concurrent operations
            sem = asyncio.Semaphore(4)  # Max 4 concurrent operations

            async def retrieve_with_semaphore(item):
                """Retrieve documents with semaphore."""
                async with sem:
                    if item.source_name not in self.all_retrievers:
                        logger.warning(f"Source {item.source_name} not found in all_retrievers due to AI select source")
                        return []

                    return await retrieve_unique_docs_by_hybrid_search(
                        item.queries,
                        doc_retriever=self.all_retrievers[item.source_name],
                    )

            # Create tasks with semaphore
            tasks = [retrieve_with_semaphore(item) for item in source_queries]

            # Wait for all tasks to complete
            all_retrieved_docs = await asyncio.gather(*tasks)

            # Rest of your processing logic remains the same
            number_of_sources = len(all_retrieved_docs)
            if number_of_sources in (1, 2):
                max_acceptable_docs = 20
            elif number_of_sources in (3, 4):
                max_acceptable_docs = 24
            elif number_of_sources in (5, 6, 7):
                max_acceptable_docs = 35
            else:
                max_acceptable_docs = 4 * number_of_sources
            number_doc_per_source = max_acceptable_docs // number_of_sources

            for docs in all_retrieved_docs:
                filtered_docs.extend(docs[:number_doc_per_source])
            if len(filtered_docs) > max_acceptable_docs:
                filtered_docs = filtered_docs[:max_acceptable_docs]

            filtered_docs, tables = reformat_and_fusion_docs(filtered_docs)
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}. Traceback: {traceback.format_exc()}")

        if state.get("analyze_table", False):
            gen_queries = [query for item in source_queries for query in item.queries]

            filtered_docs, tables = await filter_in_relevant_documents(
                state["question"],
                gen_queries,
                filtered_docs,
                tables,
            )
        return {"documents": filtered_docs, "tables": tables}
