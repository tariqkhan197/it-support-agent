"""
Vector store (ChromaDB, local persistence — free, no external service).

Stores document chunks with pre-computed embeddings (from an EmbeddingClient)
and metadata (document_id, filename, page_number) so retrieval results can
be traced back to their source PDF and page for citation in the UI.
"""

import chromadb

from backend.config.settings import get_settings
from backend.knowledge_base.embeddings import EmbeddingClient
from backend.models.knowledge import DocumentChunk, RetrievedChunk
from backend.utils.exceptions import DocumentProcessingError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class VectorStore:
    """Thin wrapper around a ChromaDB persistent collection."""

    def __init__(self, embedding_client: EmbeddingClient, persist_path: str | None = None) -> None:
        self.embedding_client = embedding_client
        self._client = chromadb.PersistentClient(path=persist_path or settings.VECTOR_STORE_PATH)
        # embedding_function=None: we always supply our own pre-computed embeddings,
        # so Chroma never tries to load a default model itself.
        self._collection = self._client.get_or_create_collection(
            name=settings.VECTOR_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[DocumentChunk], *, source_filename: str) -> int:
        """Embed and store a batch of chunks. Returns the number of chunks stored."""
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        try:
            embeddings = self.embedding_client.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001
            raise DocumentProcessingError(f"Failed to embed chunks for '{source_filename}': {exc}") from exc

        ids = [f"doc{c.document_id}-chunk{c.chunk_index}" for c in chunks]
        metadatas = [
            {
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "source_filename": source_filename,
            }
            for c in chunks
        ]

        self._collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        logger.info("Stored %d chunks for '%s' in vector store", len(chunks), source_filename)
        return len(chunks)

    def query(
        self,
        query_text: str,
        *,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        """
        Return the top_k most similar chunks to query_text, filtering out
        anything below similarity_threshold (cosine similarity, 0-1).
        """
        top_k = top_k or settings.RAG_TOP_K
        similarity_threshold = (
            similarity_threshold if similarity_threshold is not None else settings.RAG_SIMILARITY_THRESHOLD
        )

        if self._collection.count() == 0:
            return []

        query_embedding = self.embedding_client.embed_query(query_text)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[RetrievedChunk] = []
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        for document, metadata, distance in zip(documents, metadatas, distances):
            # Cosine distance -> similarity: similarity = 1 - distance
            similarity = max(0.0, 1.0 - distance)
            if similarity < similarity_threshold:
                continue
            chunks.append(
                RetrievedChunk(
                    content=document,
                    similarity_score=round(similarity, 4),
                    source_filename=metadata["source_filename"],
                    page_number=metadata["page_number"],
                    document_id=metadata["document_id"],
                )
            )

        return chunks

    def delete_document(self, document_id: int) -> int:
        """Delete all chunks belonging to a document. Returns the number of chunks removed."""
        existing = self._collection.get(where={"document_id": document_id})
        ids_to_delete = existing.get("ids", [])
        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
        logger.info("Deleted %d chunks for document_id=%s from vector store", len(ids_to_delete), document_id)
        return len(ids_to_delete)

    def total_chunk_count(self) -> int:
        return self._collection.count()
