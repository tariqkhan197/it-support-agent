"""
Knowledge-base retrieval service.

Used by the support workflow to fetch relevant context BEFORE a specialist
agent responds, so the agent can ground its answer in company documents
(policies, manuals, SOPs) instead of relying purely on general knowledge.
"""

from backend.knowledge_base.vector_store import VectorStore
from backend.models.knowledge import RetrievalResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RetrievalService:
    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store

    def retrieve(self, query: str, *, top_k: int | None = None, similarity_threshold: float | None = None) -> RetrievalResult:
        chunks = self.vector_store.query(query, top_k=top_k, similarity_threshold=similarity_threshold)

        if not chunks:
            return RetrievalResult(query=query, chunks=[], context_text="", used_knowledge_base=False)

        formatted_sections = []
        for i, chunk in enumerate(chunks, start=1):
            formatted_sections.append(
                f"[Source {i}: {chunk.source_filename}, page {chunk.page_number} "
                f"(relevance {chunk.similarity_score:.2f})]\n{chunk.content}"
            )
        context_text = "\n\n".join(formatted_sections)

        logger.info("Retrieved %d relevant chunks for query", len(chunks))
        return RetrievalResult(query=query, chunks=chunks, context_text=context_text, used_knowledge_base=True)
