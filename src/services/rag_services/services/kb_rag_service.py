import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session

from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.services.rag_services.models.graph_builder import GraphBuilder
from src.services.rag_services.services import RAGService

logger = logging.getLogger(__name__)


class KBRagService(RAGService):
	doc_retriever = DocumentRetriever.get_kb_doc_retriever()
	graph_builder = GraphBuilder(doc_retriever)

	@classmethod
	async def process_with_history(cls, query: str, session_id: Optional[str] = None, db: Session = None) -> str:
		"""Process a query using chat history context"""
		# Get or create a session ID
		if session_id is None:
			session_id = str(uuid.uuid4())
		
		# Get chat history for this session
		history = cls.get_chat_history(session_id, db=db)
		
		# Create config with the session ID as thread_id
		config = {"configurable": {"thread_id": session_id, "user_id": session_id}}
		
		# Add the current query to history
		history.add_user_message(query)
		
		# Process the query with the graph that maintains memory
		final_response = None
		
		# Stream through the graph
		input_ = {"messages": [{"role": "user", "content": query}]}
		graph = cls.init_graph()
		async for step in graph.astream(input_, config, stream_mode="values"):
			final_response = step["messages"][-1]
		
		# Add AI response to history
		if final_response:
			history.add_ai_message(str(final_response.content))
		
		return str(final_response.content) if final_response else "No response generated"
		
	@classmethod
	def get_chat_history(cls, session_id: str, db: Session = None):
		"""Get chat history for a session, using provided db session if available"""
		# Use the provided database session if available		
		return super().get_chat_history(session_id, db=db)
		
	@classmethod
	async def ask_with_memory(cls, question: str, db: Session = None) -> str:
		"""Answer a question with chat memory/history, using provided db session"""
		return await cls.process_with_history(question, db=db)
		
	@classmethod
	async def ask_with_no_memory(cls, question: str, db: Session = None) -> str:
		"""Answer a question without chat memory, using provided db session"""
		# Process the query without memory
		graph = cls.init_graph()
		response = await graph.ainvoke({"messages": [{"role": "user", "content": question}]})
		return str(response["messages"][-1].content)

