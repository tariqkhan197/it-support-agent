"""
Knowledge-base ingestion service.

Orchestrates the full RAG ingestion pipeline for one uploaded PDF:
    validate -> save to disk -> extract text -> chunk -> embed -> store

Keeps the vector store (ChromaDB) and metadata table (SQLite) in sync by
using the same document_id in both.
"""

import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.knowledge_repository import KnowledgeRepository
from backend.knowledge_base.chunker import chunk_text
from backend.knowledge_base.pdf_processor import extract_pages
from backend.knowledge_base.vector_store import VectorStore
from backend.models.knowledge import DocumentChunk, KnowledgeDocumentResponse
from backend.utils.exceptions import DocumentProcessingError, FileValidationError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


def validate_upload(filename: str, file_size_bytes: int) -> None:
    """Validate an uploaded file's extension and size before it's ever written to disk."""
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.ALLOWED_DOCUMENT_TYPES:
        raise FileValidationError(
            f"Unsupported file type '{suffix}'. Allowed types: {settings.ALLOWED_DOCUMENT_TYPES}"
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise FileValidationError(
            f"File is too large ({file_size_bytes / 1024 / 1024:.1f} MB). "
            f"Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    if file_size_bytes == 0:
        raise FileValidationError("Uploaded file is empty.")


class IngestionService:
    def __init__(self, db: Session, vector_store: VectorStore) -> None:
        self.db = db
        self.vector_store = vector_store
        self.knowledge_repo = KnowledgeRepository(db)

    def ingest_pdf(
        self,
        *,
        source_path: str | Path,
        original_filename: str,
        category: str | None = None,
        uploaded_by: str = "admin",
    ) -> KnowledgeDocumentResponse:
        """
        Ingest a PDF already saved at `source_path` (e.g. an upload written
        to a temp location). Copies it into the managed upload directory,
        extracts + chunks + embeds its text, and records everything.
        """
        source_path = Path(source_path)
        file_size_bytes = source_path.stat().st_size
        validate_upload(original_filename, file_size_bytes)

        stored_path = self._copy_into_upload_dir(source_path, original_filename)

        try:
            pages = extract_pages(stored_path)
        except DocumentProcessingError:
            stored_path.unlink(missing_ok=True)
            raise

        document = self.knowledge_repo.create_document(
            original_filename=original_filename,
            stored_file_path=str(stored_path),
            page_count=len(pages),
            file_size_bytes=file_size_bytes,
            category=category,
            uploaded_by=uploaded_by,
        )

        chunks: list[DocumentChunk] = []
        chunk_index = 0
        for page in pages:
            if not page.text:
                continue
            for piece in chunk_text(
                page.text,
                chunk_size=settings.RAG_CHUNK_SIZE,
                chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            ):
                chunks.append(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk_index,
                        content=piece,
                        page_number=page.page_number,
                    )
                )
                chunk_index += 1

        stored_count = self.vector_store.add_chunks(chunks, source_filename=original_filename)
        document = self.knowledge_repo.update_chunk_count(document.id, stored_count)

        logger.info(
            "Ingested '%s': %d pages, %d chunks", original_filename, document.page_count, stored_count
        )
        return KnowledgeDocumentResponse.model_validate(document)

    def delete_document(self, document_id: int) -> None:
        document = self.knowledge_repo.get_by_id(document_id)
        self.vector_store.delete_document(document_id)
        Path(document.stored_file_path).unlink(missing_ok=True)
        self.knowledge_repo.delete_document(document_id)

    def list_documents(self) -> list[KnowledgeDocumentResponse]:
        return [
            KnowledgeDocumentResponse.model_validate(d) for d in self.knowledge_repo.list_documents()
        ]

    @staticmethod
    def _copy_into_upload_dir(source_path: Path, original_filename: str) -> Path:
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex[:8]}_{Path(original_filename).name}"
        destination = upload_dir / safe_name
        shutil.copyfile(source_path, destination)
        return destination
