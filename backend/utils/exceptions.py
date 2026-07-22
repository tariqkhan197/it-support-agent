"""
Custom exception hierarchy.

Using typed exceptions (instead of generic Exception/ValueError everywhere)
lets the FastAPI layer map errors to correct HTTP status codes and lets
callers catch specific failure modes.
"""


class ITSupportAgentError(Exception):
    """Base class for all application-specific errors."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(ITSupportAgentError):
    """Raised when required configuration/environment values are missing or invalid."""


class LLMProviderError(ITSupportAgentError):
    """Raised when the Groq API call fails, times out, or returns an unusable response."""


class PromptInjectionDetectedError(ITSupportAgentError):
    """Raised when user input is flagged by the prompt-injection guardrail."""


class RateLimitExceededError(ITSupportAgentError):
    """Raised when a client exceeds the configured request rate limit."""


class FileValidationError(ITSupportAgentError):
    """Raised when an uploaded file fails type/size/content validation."""


class DocumentProcessingError(ITSupportAgentError):
    """Raised when a PDF fails to parse, chunk, or embed during ingestion."""


class OCRProcessingError(ITSupportAgentError):
    """Raised when OCR text extraction fails on an uploaded image."""


class TicketNotFoundError(ITSupportAgentError):
    """Raised when a requested ticket ID does not exist."""


class TicketValidationError(ITSupportAgentError):
    """Raised when ticket creation/update data fails validation or an invalid transition is attempted."""


class AuthenticationError(ITSupportAgentError):
    """Raised when admin login credentials are invalid or a session token is invalid/expired."""


class AgentRoutingError(ITSupportAgentError):
    """Raised when the supervisor agent cannot classify or route a request to a specialist agent."""


class DatabaseError(ITSupportAgentError):
    """Raised when a database operation fails unexpectedly."""
