import datetime
import logging
import uuid
from typing import Optional

import psycopg
from langchain_core.messages import AIMessage
from langchain_postgres import PostgresChatMessageHistory
from sqlalchemy.orm import Session

from src.config.fastapi_config import fastapi_settings
from src.services.postgres.models.tables.rag_sync_db.chat_history_model import (
    ChatHistory,
)
from src.services.rag_services.models.document_retriever import DocumentRetriever
from src.services.rag_services.models.graph_builder import GraphBuilder
from src.utils.streams_helper import process_citations

logger = logging.getLogger(__name__)


class RAGService:
    doc_retriever: DocumentRetriever
    graph_builder: GraphBuilder
    chat_history_table = ChatHistory.__tablename__

    # PostgreSQL connection for chat history
    pg_conn = None

    @classmethod
    def ask_with_memory(cls, question: str, db: Session = None):
        # TBD
        pass

    @classmethod
    def ask_with_no_memory(cls, question: str, db: Session = None):
        input_ = {"messages": [{"role": "user", "content": question}]}
        graph = cls.init_graph()
        state = graph.invoke(input_)

        return str(state["messages"][-1].content)

    @classmethod
    def init_graph(cls):
        graph = cls.graph_builder.built_graph.compile()
        return graph

    @classmethod
    def initialize_db_connection(cls):
        """Initialize the PostgreSQL database connection with timeout and connection pooling"""
        try:
            # Check if connection exists and is still open
            if cls.pg_conn is not None and not cls.pg_conn.closed:
                # Test if connection is actually working with a simple query
                try:
                    with cls.pg_conn.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
                    # Connection is good, no need to reconnect
                    return
                except psycopg.OperationalError:
                    # Connection is stale, close it so we can reconnect
                    logger.warning("Stale database connection detected, reconnecting...")
                    try:
                        cls.pg_conn.close()
                    except Exception:
                        pass  # Ignore errors when closing a potentially dead connection

            # Connect with timeout parameter to prevent hanging connections
            cls.pg_conn = psycopg.connect(conninfo=fastapi_settings.db.database_url)

            # Configure connection for better performance
            cls.pg_conn.autocommit = False  # Explicit transaction management

            # Ensure the chat history table exists
            logger.info("PostgreSQL connection established successfully")

        except Exception as e:
            logger.exception("Failed to initialize PostgreSQL connection: %s", e)
            if cls.pg_conn is not None:
                try:
                    cls.pg_conn.close()
                except Exception:
                    pass
            cls.pg_conn = None
            raise

    @classmethod
    def get_chat_history(cls, session_id: str | None = None, db: Session = None) -> PostgresChatMessageHistory:
        """Get a chat history instance for the given session ID"""
        if session_id is None:
            session_id = str(uuid.uuid4())
            logger.info(f"Created new session ID: {session_id}")

        # If SQLAlchemy session is provided, use it instead of direct PostgreSQL connection
        if db is not None:
            # Use the SQLAlchemy session's connection for PostgresChatMessageHistory
            try:
                # Get the underlying DBAPI connection from SQLAlchemy session
                raw_connection = db.connection().connection
                return PostgresChatMessageHistory(cls.chat_history_table, session_id, sync_connection=raw_connection)
            except Exception as e:
                logger.warning(
                    f"Failed to use SQLAlchemy session for chat history, falling back to direct connection: {e}",
                )

        # Fallback to direct PostgreSQL connection
        cls.initialize_db_connection()
        return PostgresChatMessageHistory(cls.chat_history_table, session_id, sync_connection=cls.pg_conn)

    @classmethod
    def clear_history(cls, session_id: str, db: Session = None) -> None:
        """Clear chat history for a specific session"""
        history = cls.get_chat_history(session_id, db=db)
        history.clear()
        logger.info(f"Cleared chat history for session {session_id}")

    @classmethod
    def _get_or_create_chat_history(cls, session_id, db):
        try:
            if hasattr(cls, "get_chat_history"):
                return cls.get_chat_history(session_id, db=db)
        except Exception as e:
            logger.error(f"Could not add message to chat history: {e!s}")
        return None

    @classmethod
    def _process_chunk(cls, mode, chunk, session_id):
        """Process a single chunk from the graph stream and yield results."""
        results = []
        if mode == "custom":
            generated_content = chunk.get("generate", None)
            picked_sources = chunk.get("picked_sources", None)
            save_instructions = chunk.get("save_instructions", None)
            if generated_content:
                results.append({"msg": generated_content, "session_id": session_id})
            if picked_sources:
                results.append({"picked_sources": picked_sources, "session_id": session_id})
            if save_instructions is not None:
                results.append({"save_instructions": save_instructions, "session_id": session_id})
            if chunk.get("documents", None):
                documents = chunk["documents"]
                citations = process_citations(documents)
                results.append({"citation": citations, "session_id": session_id})
        elif mode == "values" and chunk.get("generate", None):
            documents = chunk["documents"]
            citations = process_citations(documents)
            results.append({"citation": citations, "session_id": session_id})
        return results

    @classmethod
    def _add_to_history(cls, history, question, complete_response, user_id):
        try:
            history.add_user_message(question)
            full_response = "".join(complete_response)
            if full_response.strip() and full_response.strip() != "*":
                ai_message = AIMessage(
                    content=full_response,
                    additional_kwargs={
                        "timestamp": datetime.datetime.now().isoformat(),
                        "user_id": user_id,
                    },
                )
                history.add_message(ai_message)
            return full_response
        except Exception as e:
            logger.error(f"Could not add AI response to chat history: {e!s}")
            return ""

    @classmethod
    async def stream_response(
        cls,
        question: str,
        session_id: str | None = None,
        user_id: str | None = None,
        user_name: str | None = None,
        analyze_table=False,
        db: Session | None = None,
        **input_kwargs,
    ):
        """Stream response with chat history support if available."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        using_memory = input_kwargs.get("using_memory", True)
        config = {
            "configurable": {
                "thread_id": session_id,
                "user_id": user_id,
                "user_name": user_name or "Unknown",
                "session_id": session_id,
            },
        }
        if user_name:
            config["configurable"]["user_name"] = user_name

        history = cls._get_or_create_chat_history(session_id, db) if using_memory else None

        input_ = {
            "messages": [{"role": "user", "content": question}],
            "analyze_table": analyze_table,
            "chat_state": dict(conversation_id=session_id),
            **input_kwargs,
        }

        complete_response = []
        graph = cls.init_graph()
        async for mode, chunk in graph.astream(input_, config=config, stream_mode=["custom", "values"]):
            results = cls._process_chunk(mode, chunk, session_id)
            for result in results:
                if "msg" in result:
                    complete_response.append(result["msg"])
                yield result

        if complete_response and history and using_memory:
            full_response = cls._add_to_history(history, question, complete_response, user_id)
            yield {"full_response": full_response, "session_id": session_id}
