from sqlalchemy.orm import Session

from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.services.rag_services.models.graph_builder import GraphBuilder


class DynamicRagService:
    def __init__(self, collection_name: str):
        super().__init__()
        doc_retriever = DocumentRetriever.get_doc_retriever(collection_name)
        graph_builder = GraphBuilder(doc_retriever)
        self.graph_no_memory = graph_builder.built_graph.compile()
        
    async def ask_with_no_memory(
        self, question: str, db: Session = None, analyze_mode: bool = False
    ) -> str:
        final_response = None
        # Stream through the graph

        input_ = {
            "messages": [{"role": "user", "content": question}],
            "analyze_table": analyze_mode,
        }
        async for step in self.graph_no_memory.astream(input_, stream_mode="values"):
            final_response = step["messages"][-1]

        return str(final_response.content)
