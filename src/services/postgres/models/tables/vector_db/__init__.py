from sqlalchemy import Column, ForeignKey, ARRAY, String, JSON, REAL
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.config.database_config import Base


class MyEmbeddingStore(Base):
    """Exact copy of EmbeddingStore model from langchain"""

    __tablename__ = "langchain_embeddings"

    uuid = Column(String, primary_key=True)
    embedding = Column(ARRAY(REAL))
    document = Column(String)
    cmetadata = Column(JSON)
    custom_id = Column(String)
    collection_id = Column(String, ForeignKey("langchain_collections.uuid"))
    collection = relationship("MyCollectionStore", back_populates="embeddings")


class MyCollectionStore(Base):
    """Exact copy of CollectionStore model from langchain"""

    __tablename__ = "langchain_collections"

    uuid = Column(String, primary_key=True)
    name = Column(String)
    cmetadata = Column(JSON)
    embeddings = relationship(
        "MyEmbeddingStore", back_populates="collection", cascade="all, delete-orphan"
    )
