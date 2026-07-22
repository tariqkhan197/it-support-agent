"""
Knowledge base management routes.

Uploading and deleting documents are admin-only actions (the KB shapes
what every employee's chat answers are grounded in); listing is available
to any authenticated context that needs to display what's indexed.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from backend.api.auth_utils import get_current_admin
from backend.api.dependencies import get_vector_store
from backend.database.session import get_db
from backend.knowledge_base.ingestion_service import IngestionService
from backend.knowledge_base.vector_store import VectorStore
from backend.models.knowledge import KnowledgeDocumentResponse

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


@router.post("/upload", response_model=KnowledgeDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    admin: str = Depends(get_current_admin),
) -> KnowledgeDocumentResponse:
    """Upload a PDF into the knowledge base: extracted, chunked, embedded, and indexed. Admin only."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        service = IngestionService(db, vector_store)
        return service.ingest_pdf(
            source_path=tmp_path,
            original_filename=file.filename,
            category=category,
            uploaded_by=admin,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
async def list_documents(
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    _admin: str = Depends(get_current_admin),
) -> list[KnowledgeDocumentResponse]:
    """List all documents currently indexed in the knowledge base. Admin only."""
    return IngestionService(db, vector_store).list_documents()


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    _admin: str = Depends(get_current_admin),
) -> dict:
    """Delete a document and all its vectors from the knowledge base. Admin only."""
    IngestionService(db, vector_store).delete_document(document_id)
    return {"deleted": True, "document_id": document_id}
