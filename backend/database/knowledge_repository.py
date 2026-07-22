"""
Knowledge document repository.

Manages the SQLite metadata rows for uploaded PDFs. The vector store
(ChromaDB) is managed separately in vector_store.py; the ingestion_service
keeps the two in sync (same document_id used in both).
"""

from sqlalchemy.orm import Session

from backend.database.models import KnowledgeDocument
from backend.utils.exceptions import ITSupportAgentError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeDocumentNotFoundError(ITSupportAgentError):
    """Raised when a requested knowledge document ID does not exist."""


class KnowledgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_document(
        self,
        *,
        original_filename: str,
        stored_file_path: str,
        page_count: int,
        file_size_bytes: int,
        category: str | None = None,
        uploaded_by: str = "admin",
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            original_filename=original_filename,
            stored_file_path=stored_file_path,
            category=category,
            page_count=page_count,
            chunk_count=0,  # updated after chunks are embedded
            file_size_bytes=file_size_bytes,
            uploaded_by=uploaded_by,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        logger.info("Registered knowledge document '%s' (id=%s)", original_filename, document.id)
        return document

    def update_chunk_count(self, document_id: int, chunk_count: int) -> KnowledgeDocument:
        document = self.get_by_id(document_id)
        document.chunk_count = chunk_count
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_by_id(self, document_id: int) -> KnowledgeDocument:
        document = self.db.get(KnowledgeDocument, document_id)
        if document is None:
            raise KnowledgeDocumentNotFoundError(f"Knowledge document {document_id} not found")
        return document

    def list_documents(self) -> list[KnowledgeDocument]:
        return self.db.query(KnowledgeDocument).order_by(KnowledgeDocument.uploaded_at.desc()).all()

    def delete_document(self, document_id: int) -> KnowledgeDocument:
        document = self.get_by_id(document_id)
        self.db.delete(document)
        self.db.commit()
        logger.warning("Deleted knowledge document '%s' (id=%s)", document.original_filename, document_id)
        return document
