import logging
import traceback

import yaml
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai.chat_models.base import BaseChatOpenAI
from langgraph.graph import StateGraph
from langgraph.types import StreamWriter

from src.services.custom_llm.services.llm_utils import LLMUtils
from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.services.rag_services.models.graph_builder.nodes.analysis_table import (
    analysis_table,
)
from src.services.rag_services.models.graph_builder.nodes.classify_message import (
    classify_message_node,
)
from src.services.rag_services.models.graph_builder.nodes.create_queries import (
    create_queries,
)
from src.services.rag_services.models.graph_builder.nodes.fetch_user_data import (
    fetch_conversation_data,
)
from src.services.rag_services.models.graph_builder.nodes.generate import generate
from src.services.rag_services.models.graph_builder.nodes.retriever import retriever
from src.services.rag_services.models.graph_builder.nodes.save_instructions import (
    save_instruction_prompts,
)
from src.services.rag_services.models.graph_builder.state import GraphState

logger = logging.getLogger(__name__)


class GraphBuilder:
    def __init__(
        self,
        doc_retriever: DocumentRetriever | None = None,
        llm: BaseChatOpenAI | None = None,
    ):
        self.doc_retriever = doc_retriever
        self.llm = llm or LLMUtils.get_azure_openai_llm()
        self._graph_builder = StateGraph(GraphState)
        self._define_nodes()

    async def create_queries(self, state: GraphState):
        """Generate tool call for retrieval."""
        if state["classification_message"] in ("feedback", "greeting"):
            return {}

        human_message = self._get_latest_human_message(state["messages"])
        histories = state.get("history", [])[-10:]
        response = await create_queries(
            human_message=human_message,
            histories=histories,
        )

        return {"gen_queries": response}

    @staticmethod
    def _should_analysis_tables(state):
        try:
            tables = state.get("tables", [])
            can_analyze = state.get("analyze_table", False)
            if not tables or not can_analyze:
                return "generate"
            return "analysis_tables"
        except Exception as e:
            logger.error(
                f"Error in _should_analysis_tables: {e}. Traceback: {traceback.format_exc()}",
            )

        return "generate"

    @staticmethod
    async def _generate(state: GraphState, writer: StreamWriter):
        """Generate answer."""
        response: str = await generate(state, writer)

        return {"messages": [AIMessage(content=response)]}

    async def _retrieve_by_hybrid_search(self, state: GraphState):
        """Retrieve relevant documents based on English search queries and the original user question."""
        english_queries = state.get("gen_queries", [])
        retrieved_docs, tables = await retriever(
            human_message=state["question"],
            english_queries=english_queries,
            doc_retriever=self.doc_retriever,
            analyze_mode=state.get("analyze_table", False),
        )

        return dict(documents=retrieved_docs, tables=tables)

    @staticmethod
    async def _analysis_tables(state: GraphState):
        """Analyze tables and format results for LLM consumption"""
        tables = state.get("tables", [])
        can_analyze = state.get("analyze_table", False)
        human_message = state["question"]

        return analysis_table(can_analyze, human_message, tables)

    @staticmethod
    def _get_latest_human_message(state_messages) -> str:
        human_message = next(
            (message.content for message in reversed(state_messages) if isinstance(message, HumanMessage)),
            "",
        )
        if isinstance(human_message, str):
            return human_message
        raise ValueError("No human message is string type in state messages")

    @staticmethod
    async def _save_instructions(state: GraphState, writer: StreamWriter):
        conversation_id = state.get("chat_state", {}).get("conversation_id")
        if not conversation_id:
            return None
        if state["classification_message"] not in ("feedback", "mixed_feedback"):
            return None

        writer({"save_instructions": "Updating memory..."})
        histories = state.get("history", [])[-10:]
        response = save_instruction_prompts(
            conversation_id=conversation_id,
            user_message=state["question"],
            histories=histories,
        )
        node_message = "I have update my memory with your feedback. This is what i updated:\n"
        update_process = yaml.dump(response.model_dump())
        node_message += update_process
        writer({"save_instructions": "Updating memory: Done!"})

        return {
            "debug": response.model_dump() if response else None,
            "node_message": {"save_instructions": node_message},
        }

    async def classify_message(self, state: GraphState):
        """Classify the user message into a specific category."""
        human_message = self._get_latest_human_message(state["messages"])

        if state.get("using_memory", True):
            response = await classify_message_node(human_message)
            return {"classification_message": response}

        return {"classification_message": "message"}

    async def fetch_conversation_data(self, state: GraphState):
        """Fetch conversation data from the database. Include: chat_histories and persona instruction."""
        conversation_id = state.get("chat_state", {}).get("conversation_id")
        human_message = self._get_latest_human_message(state["messages"])
        if not conversation_id:
            return {"history": [], "instructions": [], "question": human_message}
        if state.get("using_memory", True):
            last_20_messages, prompts = await fetch_conversation_data(
                conversation_id=conversation_id,
                k=20,
            )
        else:
            last_20_messages, prompts = [], []

        return {
            "history": last_20_messages,
            "instructions": prompts,
            "question": human_message,
        }

    def _define_nodes_without_generate(self):
        """Define and connect all nodes in the graph."""
        self._graph_builder.add_node(
            "fetch_conversation_data",
            self.fetch_conversation_data,
        )
        self._graph_builder.add_node("classify_message", self.classify_message)
        self._graph_builder.add_node("create_queries", self.create_queries)
        self._graph_builder.add_node("retriever", self._retrieve_by_hybrid_search)
        self._graph_builder.add_node("save_instructions", self._save_instructions)

        # Set entry point and edges
        self._graph_builder.set_entry_point("fetch_conversation_data")
        self._graph_builder.add_edge("fetch_conversation_data", "classify_message")
        self._graph_builder.add_edge("classify_message", "create_queries")
        self._graph_builder.add_edge("classify_message", "save_instructions")
        self._graph_builder.add_edge("create_queries", "retriever")
        self._graph_builder.add_edge("save_instructions", "retriever")

        self._graph_builder.set_finish_point("retriever")

    def _define_nodes(self):
        """Define and connect all nodes in the graph."""
        self._graph_builder.add_node(
            "fetch_conversation_data",
            self.fetch_conversation_data,
        )
        self._graph_builder.add_node("classify_message", self.classify_message)
        self._graph_builder.add_node("create_queries", self.create_queries)
        self._graph_builder.add_node("retriever", self._retrieve_by_hybrid_search)
        self._graph_builder.add_node("analysis_tables", self._analysis_tables)
        self._graph_builder.add_node("save_instructions", self._save_instructions)
        self._graph_builder.add_node("generate", self._generate)

        # Set entry point and edges
        self._graph_builder.set_entry_point("fetch_conversation_data")
        self._graph_builder.add_edge("fetch_conversation_data", "classify_message")
        self._graph_builder.add_edge("classify_message", "create_queries")
        self._graph_builder.add_edge("classify_message", "save_instructions")
        self._graph_builder.add_edge("create_queries", "retriever")
        self._graph_builder.add_edge("save_instructions", "retriever")
        self._graph_builder.add_edge("retriever", "analysis_tables")

        self._graph_builder.add_edge("analysis_tables", "generate")
        self._graph_builder.set_finish_point("generate")

    @property
    def built_graph(self):
        """Return the configured graph."""
        return self._graph_builder
