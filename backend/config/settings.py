"""
Application configuration.

All configuration is centralized here using Pydantic V2's BaseSettings.
Values are loaded from environment variables (and a local .env file during
development). Nothing sensitive is hard-coded — see .env.example for the
full list of variables this application expects.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: backend/config/settings.py -> backend/config -> backend -> project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Strongly-typed application settings.

    Every field has either a safe default or is required via the environment.
    This class is instantiated once (see get_settings()) and reused across
    the whole application (backend API, Streamlit frontend, agents, etc.).
    """

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- General ----
    APP_NAME: str = "AI IT Support Agent"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    SECRET_KEY: str = Field(
        default="change-me-in-production",
        description="Used for signing admin session tokens.",
    )

    # ---- LLM Provider (Groq - free tier) ----
    GROQ_API_KEY: str = Field(default="", description="Groq API key (free at console.groq.com)")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_MODEL_FAST: str = "llama-3.1-8b-instant"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048
    LLM_REQUEST_TIMEOUT: int = 60

    # ---- Embeddings (local, free — sentence-transformers) ----
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ---- Database ----
    DATABASE_PATH: str = str(BASE_DIR / "data" / "it_support.db")

    # ---- Vector Store (ChromaDB, local persistence) ----
    VECTOR_STORE_PATH: str = str(BASE_DIR / "data" / "vectorstore")
    VECTOR_COLLECTION_NAME: str = "it_knowledge_base"
    RAG_TOP_K: int = 4
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 150
    RAG_SIMILARITY_THRESHOLD: float = 0.35

    # ---- File uploads ----
    UPLOAD_DIR: str = str(BASE_DIR / "data" / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_DOCUMENT_TYPES: tuple[str, ...] = (".pdf",)
    ALLOWED_IMAGE_TYPES: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

    # ---- OCR ----
    TESSERACT_CMD: str = Field(
        default="tesseract",
        description="Path to the tesseract binary. Override on Windows.",
    )

    # ---- Admin auth ----
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = Field(
        default="",
        description="bcrypt hash of the admin password. Generate via scripts/hash_password.py",
    )
    SESSION_EXPIRY_MINUTES: int = 120

    # ---- Rate limiting ----
    RATE_LIMIT_REQUESTS: int = 30
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ---- API ----
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]

    # ---- Logging ----
    LOG_DIR: str = str(BASE_DIR / "logs")
    LOG_LEVEL: str = "INFO"
    LOG_FILE_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
    LOG_FILE_BACKUP_COUNT: int = 5

    @field_validator("DATABASE_PATH", "VECTOR_STORE_PATH", "UPLOAD_DIR", "LOG_DIR")
    @classmethod
    def _ensure_parent_dir_exists(cls, value: str) -> str:
        """Guarantee that directories required by the app exist at startup."""
        path = Path(value)
        target_dir = path if path.suffix == "" else path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        return value


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Using lru_cache means the .env file / environment is only parsed once
    per process, and every module that calls get_settings() shares the
    same configuration object.
    """
    return Settings()
