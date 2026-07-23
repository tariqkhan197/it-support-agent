"""
Lightweight OCR service for resource-constrained environments (Render Free Tier 512MB RAM).
"""

from pathlib import Path
from backend.config.settings import get_settings
from backend.utils.exceptions import FileValidationError, OCRProcessingError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


def validate_image_upload(filename: str, file_size_bytes: int) -> None:
    """Validate an uploaded screenshot's extension and size before processing."""
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.ALLOWED_IMAGE_TYPES:
        raise FileValidationError(
            f"Unsupported image type '{suffix}'. Allowed types: {settings.ALLOWED_IMAGE_TYPES}"
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise FileValidationError(
            f"Image is too large ({file_size_bytes / 1024 / 1024:.1f} MB). "
            f"Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    if file_size_bytes == 0:
        raise FileValidationError("Uploaded image is empty.")


def extract_text_from_image(image_path: str | Path) -> str:
    """
    Safely process screenshot path for AI Vision analysis without loading heavy OCR binaries.
    """
    path = Path(image_path)
    if not path.exists():
        raise OCRProcessingError(f"Image file not found: {path}")

    logger.info("Screenshot received successfully: '%s'", path.name)
    
    # Clean string signal so AI Agent directly analyzes image visually
    return f"[Uploaded Image: {path.name}] Analyzing screenshot directly using multimodal vision diagnostics."