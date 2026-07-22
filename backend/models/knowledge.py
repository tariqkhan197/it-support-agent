"""
Knowledge-base domain models (Pydantic V2).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    category: str | None
    page_count: int
    chunk_count: int
    file_size_bytes: int
    uploaded_by: str
    uploaded_at: datetime


class DocumentChunk(BaseModel):
    """A single chunk produced during ingestion, ready to be embedded and stored."""

    document_id: int
    chunk_index: int
    content: str
    page_number: int


class RetrievedChunk(BaseModel):
    """A chunk returned from a similarity search, with its relevance score and source."""

    content: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    source_filename: str
    page_number: int
    document_id: int


class RetrievalResult(BaseModel):
    """The full result of a knowledge-base query — used to build agent context and cite sources."""

    query: str
    chunks: list[RetrievedChunk]
    context_text: str
    used_knowledge_base: bool
