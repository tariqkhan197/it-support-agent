"""
Shared FastAPI dependencies.

LLM client, embedding client, vector store, and retrieval service are all
expensive-ish to construct (or, for the embedding model, lazily loaded on
first real use) so each is built once per process via lru_cache and
injected wherever needed.
"""

from functools import lru_cache

from backend.knowledge_base.embeddings import SentenceTransformerEmbeddings
from backend.knowledge_base.retrieval_service import RetrievalService
from backend.knowledge_base.vector_store import VectorStore
from backend.utils.llm_client import GroqLLMClient


@lru_cache
def get_llm_client() -> GroqLLMClient:
    return GroqLLMClient()


@lru_cache
def get_embedding_client() -> SentenceTransformerEmbeddings:
    return SentenceTransformerEmbeddings()


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore(get_embedding_client())


@lru_cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService(get_vector_store())
