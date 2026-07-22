"""
RAG pipeline smoke test.

Uses a FakeEmbeddingClient (satisfies the EmbeddingClient protocol) so the
full ingestion -> storage -> retrieval pipeline is verified against a REAL
local ChromaDB instance, without needing network access to download
sentence-transformers model weights (blocked in this sandbox).

The fake embedding is a simple deterministic bag-of-words hashing scheme:
texts sharing more vocabulary end up with higher cosine similarity, which
is enough to prove retrieval, ranking, and thresholding all work correctly.
"""

import hashlib
import math
import re

from backend.database.session import db_session, init_db
from backend.knowledge_base.ingestion_service import IngestionService
from backend.knowledge_base.retrieval_service import RetrievalService
from backend.knowledge_base.vector_store import VectorStore

EMBED_DIM = 128


class FakeEmbeddingClient:
    """Deterministic hashing-based embeddings — no model download required."""

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * EMBED_DIM
        words = re.findall(r"[a-z0-9]+", text.lower())
        for word in words:
            digest = hashlib.md5(word.encode()).hexdigest()
            index = int(digest, 16) % EMBED_DIM
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)


def run():
    init_db()
    fake_embeddings = FakeEmbeddingClient()
    vector_store = VectorStore(fake_embeddings, persist_path="/tmp/test_vectorstore")

    with db_session() as db:
        ingestion = IngestionService(db, vector_store)

        doc = ingestion.ingest_pdf(
            source_path="/tmp/vpn_guide.pdf",
            original_filename="Company_VPN_Setup_Guide.pdf",
            category="vpn",
            uploaded_by="admin",
        )
        print(f"Ingested: {doc.original_filename} | pages={doc.page_count} chunks={doc.chunk_count}")
        assert doc.page_count == 2
        assert doc.chunk_count >= 2

        docs = ingestion.list_documents()
        print(f"Documents in KB: {[d.original_filename for d in docs]}")
        assert len(docs) == 1

        retrieval = RetrievalService(vector_store)

        # Query closely matching page 2 vocabulary (error 809, firewall, ports)
        result = retrieval.retrieve("I'm getting VPN error 809 what should I do")
        print(f"\nQuery: 'VPN error 809' -> used_kb={result.used_knowledge_base}, chunks={len(result.chunks)}")
        for c in result.chunks:
            print(f"  - page {c.page_number}, score {c.similarity_score}: {c.content[:60]}...")
        assert result.used_knowledge_base is True
        assert any(c.page_number == 2 for c in result.chunks), "Expected page 2 (error 809 section) to be retrieved"

        # Query with irrelevant vocabulary should be filtered by similarity threshold
        result2 = retrieval.retrieve("what is the capital of France and best pizza toppings")
        print(f"\nQuery: unrelated topic -> used_kb={result2.used_knowledge_base}, chunks={len(result2.chunks)}")
        assert result2.used_knowledge_base is False, "Unrelated query should be filtered out by similarity threshold"

        # Deletion removes both metadata and vectors
        ingestion.delete_document(doc.id)
        remaining_docs = ingestion.list_documents()
        remaining_chunks = vector_store.total_chunk_count()
        print(f"\nAfter delete: documents={len(remaining_docs)}, vector_chunks={remaining_chunks}")
        assert len(remaining_docs) == 0
        assert remaining_chunks == 0

    print("\nALL RAG PIPELINE CHECKS PASSED")


if __name__ == "__main__":
    run()
