from sqlalchemy.orm import Session

from src.services.rag_services.services import RAGService
from src.services.rag_services.services.multiple_rag_sources.graph_builder import GraphBuilderMultiRagSource


class MultiRagService(RAGService):
    graph_builder = GraphBuilderMultiRagSource(True)

    def __init__(self, is_using_generate_node: bool = True):
        if not is_using_generate_node:
            self.graph_builder = GraphBuilderMultiRagSource(False)

    @classmethod
    async def ask_with_no_memory_multi(
        cls,
        question: str,
        rag_sources: list[dict],
        db: Session | None = None,
        analyze_mode: bool = False,
    ):
        """Get response without memory context from multiple RAG sources.

        Args:
            question: The question to answer
            rag_sources: List of RAG source dictionaries with format: {"source_name": "Source Name"}
            db: Optional database session
            analyze_mode: Whether to analyze tables in the response


        Returns:
            str: The response text


        """
        final_response = None
        # Stream through the graph

        input_ = {
            "messages": [{"role": "user", "content": question}],
            "requested_sources": rag_sources,
            "analyze_table": analyze_mode,
        }
        graph = cls.init_graph()
        async for step in graph.astream(input_, stream_mode="values"):
            if step.get("messages"):
                final_response = step["messages"][-1]
        return str(final_response.content) if final_response else f"No response generated for the question: {question}"

    @classmethod
    async def stream_response(
        cls,
        question: str,
        session_id: str | None = None,
        user_id: str | None = None,
        user_name: str | None = None,
        db: Session = None,
        **input_kwargs,
    ):
        """Stream the response from the graph."""
        data_sources = input_kwargs.pop("data_sources", [])
        # Get the true data_sources
        analysis_mode: bool = input_kwargs.pop("analysis_mode", False)
        # Stream through the graph
        async for response in super().stream_response(
            question,
            session_id,
            user_id,
            user_name,
            requested_sources=data_sources,
            analyze_table=analysis_mode,
            using_memory=False,
            language=input_kwargs.pop("language", "en"),
            db=db,
            full_response=input_kwargs.pop("full_response", []),
        ):
            yield response
