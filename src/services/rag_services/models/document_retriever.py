import asyncio
import logging
import threading
from typing import Self

from langchain_postgres.vectorstores import PGVector
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql.expression import text

from src.config.fastapi_config import fastapi_settings
from src.config.settings import azure_openai_endpoint, embedding_deployment
from src.constants.llm_constant import AZURE_EMBEDDING
from src.constants.rag_company_constant import VectorStoreDefaultCollection
from src.services.rag_services.models.doc_processor_element import DocProcessorElement

_logger = logging.getLogger("DocumentRetriever")


class DatabaseEngineManager:
    """Thread-safe singleton manager for database engines using lazy initialization."""

    _instance: Self | None = None
    _lock = threading.Lock()

    def __new__(cls) -> Self:
        """Ensure only one instance of the manager exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the database engines and session makers."""
        if getattr(self, "_initialized", False):
            return

        self._sync_engine = None
        self._async_engine = None
        self._async_session_maker = None
        self._engine_lock = threading.Lock()
        self._initialized = True

    def get_sync_engine(self) -> Engine:
        """Get or create the synchronous database engine."""
        if self._sync_engine is None:
            with self._engine_lock:
                if self._sync_engine is None:
                    try:
                        self._sync_engine = create_engine(
                            fastapi_settings.db.vector_db_url,
                            **fastapi_settings.db.engine_options,
                        )
                        _logger.info("Synchronous database engine created successfully")
                    except Exception as e:
                        _logger.error(f"Failed to create synchronous engine: {e}")
                        raise
        return self._sync_engine

    def get_async_engine(self) -> AsyncEngine:
        """Get or create the asynchronous database engine."""
        if self._async_engine is None:
            with self._engine_lock:
                if self._async_engine is None:
                    try:
                        if fastapi_settings.db.database_ssl_context:
                            self._async_engine = create_async_engine(
                                fastapi_settings.db.vector_db_url_async,
                                connect_args={
                                    "ssl": fastapi_settings.db.database_ssl_context,
                                },
                                **fastapi_settings.db.engine_options,
                            )
                        else:
                            self._async_engine = create_async_engine(
                                fastapi_settings.db.vector_db_url_async,
                                **fastapi_settings.db.engine_options,
                            )
                        _logger.info("Asynchronous database engine created successfully")
                    except Exception as e:
                        _logger.error(f"Failed to create asynchronous engine: {e}")
                        raise
        return self._async_engine

    def get_async_session_maker(self):
        """Get or create the async session maker."""
        if self._async_session_maker is None:
            with self._engine_lock:
                if self._async_session_maker is None:
                    try:
                        self._async_session_maker = async_sessionmaker(
                            self.get_async_engine(),
                            class_=AsyncSession,
                            expire_on_commit=False,
                        )
                        _logger.info("Async session maker created successfully")
                    except Exception as e:
                        _logger.error(f"Failed to create async session maker: {e}")
                        raise
        return self._async_session_maker

    def close_engines(self) -> None:
        """Close all database engines - useful for cleanup in tests or shutdown."""
        with self._engine_lock:
            if self._sync_engine:
                self._sync_engine.dispose()
                self._sync_engine = None
                _logger.info("Synchronous engine closed")

            if self._async_engine:
                # For async engines, we need to handle cleanup differently
                # This should be called from an async context
                self._async_engine = None
                _logger.info("Asynchronous engine reference cleared")

            self._async_session_maker = None


# Global instance for easy access
_db_manager = DatabaseEngineManager()


class DocumentRetriever:
    """Class to retrieve and manage documents in a vector store."""

    # Class constants
    BATCH_SIZE = 50
    BATCH_SLEEP_SECONDS = 3

    def __init__(
        self,
        endpoint: str,
        embedding_deployment: str,
        collection_name,
        collection_base_name: str | None = None,
        is_user_collection: bool = False,
    ) -> None:
        """Initialize the DocumentRetriever with vector store settings."""
        self.endpoint = endpoint
        self.embedding_deployment = embedding_deployment
        self.collection_name = collection_name
        self.is_user_collection = is_user_collection
        self.collection_base_name = collection_base_name
        self.id_key = "doc_id"
        self.embedding = AZURE_EMBEDDING
        self.vector_store = self._initialize_vector_store()

    @property
    def async_session_maker(self):
        """Get the async session maker from the database engine manager."""
        return _db_manager.get_async_session_maker()

    def _initialize_vector_store(self) -> PGVector:
        """Initialize PGVector store with the specified collection."""
        vector_store = PGVector(
            connection=_db_manager.get_async_engine(),
            collection_name=self.collection_name,
            embeddings=self.embedding,
            pre_delete_collection=False,
            async_mode=True,
            create_extension=False,
        )
        return vector_store

    @staticmethod
    def __parse_doc_metadata(topic_name: str | None, view_url: str | None, text, metadata, doc_type=None, base64=None):
        for key, value in metadata.items():
            if isinstance(value, list):
                metadata[key] = ", ".join(value)
            else:
                metadata[key] = str(value)
        if base64:
            metadata["base64"] = base64
        table_data = text if doc_type == "table" else None
        return metadata | {
            "topic": topic_name,
            "view_url": view_url,
            "table": table_data,
        }

    async def add_documents(
        self,
        texts: list[DocProcessorElement],
        document_name: str,
        doc_type: str = "text",
        topic_name: str | None = None,
        view_url: str | None = None,
    ):
        """Add documents to the vector store asynchronously"""
        try:
            if not texts or not any(t.text.strip() for t in texts if hasattr(t, "text")):
                return  # Skip if no valid content

            def update_table_content(item) -> str:
                metadata = item.metadata
                if doc_type != "table":
                    return item.text
                topic = topic_name
                titles = metadata.get("titles")
                content = item.text
                if topic:
                    content = f"{topic}: {content}"
                if titles:
                    titles_str = ", ".join(titles)
                    content = f"{titles_str}: {content}"
                return content

            doc_texts = list(map(update_table_content, texts))
            metadata = [
                {"document_name": document_name, "type": doc_type}
                | self.__parse_doc_metadata(
                    topic_name,
                    view_url,
                    t.text,
                    t.metadata,
                    doc_type,
                    t.base64,
                )
                for t in texts
            ]
            if doc_texts:
                try:
                    total_docs = len(doc_texts)
                    for i in range(0, total_docs, self.BATCH_SIZE):
                        _logger.info(f"\tAdding documents {i} to {i + self.BATCH_SIZE} / {total_docs}")
                        batch_texts = doc_texts[i : i + self.BATCH_SIZE]
                        batch_metadata = metadata[i : i + self.BATCH_SIZE]
                        await self.vector_store.aadd_texts(texts=batch_texts, metadatas=list(batch_metadata))
                        await asyncio.sleep(self.BATCH_SLEEP_SECONDS)
                except Exception:
                    await self.remove_documents(document_name)
                    raise
        except Exception:
            _logger.exception(f"Add documents failed for {document_name}")
            raise

    async def update_documents(
        self,
        texts: list[DocProcessorElement],
        document_name: str,
        doc_type: str = "text",
    ):
        """Update documents by removing and re-adding them asynchronously."""
        try:
            await self.remove_documents(document_name)
            await self.add_documents(texts, document_name, doc_type)
        except Exception:
            _logger.exception(f"Update failed for {document_name}")
            raise

    async def remove_documents(self, doc_id_prefix: str) -> bool:
        """Remove documents from the vector store by prefix asynchronously."""
        try:
            # Use async session
            _logger.info(f"Removing documents with prefix: {doc_id_prefix}")
            async with self.async_session_maker() as session:
                collection_id_query = await session.execute(
                    text("SELECT uuid FROM langchain_pg_collection WHERE name = :collection_name"),
                    {"collection_name": self.collection_name},
                )
                collection_id = collection_id_query.scalar_one()

                ids_query = await session.execute(
                    text(
                        "SELECT id FROM langchain_pg_embedding "
                        "WHERE collection_id = :collection_id "
                        "AND cmetadata ->>'document_name' LIKE :doc_id_pattern",
                    ),
                    {
                        "collection_id": collection_id,
                        "doc_id_pattern": f"{doc_id_prefix}%",
                    },
                )
                ids_to_delete = list(ids_query.scalars().all())

                if ids_to_delete:
                    await self.vector_store.adelete(ids=ids_to_delete)
                    return True
                return False
        except Exception:
            _logger.exception(f"Remove failed for prefix {doc_id_prefix}")
            return False

    async def adelete_collection(self) -> None:
        """Delete the vector store collection asynchronously."""
        await self.vector_store.adelete_collection()

    @staticmethod
    def get_doc_retriever(dataset_key: str):
        """Get a document retriever based on dataset key asynchronously."""
        return DocumentRetriever.create_doc_retriever(dataset_key)

    @staticmethod
    def get_kb_doc_retriever():
        """Get a knowledge base document retriever synchronously."""
        return DocumentRetriever.create_doc_retriever(
            VectorStoreDefaultCollection.KB.value,
        )

    @staticmethod
    def create_doc_retriever(
        collection_name: str,
        collection_base_name: str | None = None,
        is_user_collection: bool = False,
    ):
        """Create a DocumentRetriever instance."""
        return DocumentRetriever(
            endpoint=azure_openai_endpoint,
            embedding_deployment=embedding_deployment,
            collection_name=collection_name,
            collection_base_name=collection_base_name,
            is_user_collection=is_user_collection,
        )
