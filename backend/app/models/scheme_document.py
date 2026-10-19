from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database.base import Base


class SchemeDocument(Base):
    """A versioned, provenance-bearing extraction from an official scheme source."""

    __tablename__ = "scheme_documents"
    __table_args__ = (UniqueConstraint("scheme_id", "content_sha256", name="uq_scheme_document_content"),)

    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False, index=True)
    source_name = Column(String(200), nullable=False)
    source_url = Column(String(1000), nullable=False)
    title = Column(String(500), nullable=True)
    content_sha256 = Column(String(64), nullable=False)
    extracted_text = Column(Text, nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ingestion_status = Column(String(30), nullable=False, default="completed", server_default="completed")
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    document_type = Column(String(50), nullable=True, default="official_document", server_default="official_document")
    version = Column(Integer, nullable=False, default=1, server_default="1")

    chunks = relationship("SchemeDocumentChunk", back_populates="document", cascade="all, delete-orphan", order_by="SchemeDocumentChunk.ordinal")
    scheme = relationship("Scheme", back_populates="documents")


class SchemeDocumentChunk(Base):
    __tablename__ = "scheme_document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "ordinal", name="uq_document_chunk_ordinal"),)

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("scheme_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    embedding = Column(JSON, nullable=True)
    document = relationship("SchemeDocument", back_populates="chunks")
