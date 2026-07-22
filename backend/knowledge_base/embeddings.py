"""
Embedding client.

Wraps sentence-transformers with lazy model loading (same pattern as
GroqLLMClient) and exposes an `EmbeddingClient` Protocol so the vector
store and ingestion pipeline depend on an interface, not a concrete
implementation — this allows tests to inject a deterministic fake without
downloading model weights.
"""

from typing import Protocol

from backend.config.settings import get_settings
from backend.utils.exceptions import DocumentProcessingError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class EmbeddingClient(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbeddings:
    """Production embedding client using a local, free sentence-transformers model."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model = None  # lazy-loaded on first use

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model '%s' (first use, may take a moment)...", self.model_name)
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:  # noqa: BLE001
                raise DocumentProcessingError(
                    f"Failed to load embedding model '{self.model_name}': {exc}"
                ) from exc
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        model = self._get_model()
        embedding = model.encode([text], show_progress_bar=False, normalize_embeddings=True)
        return embedding[0].tolist()
