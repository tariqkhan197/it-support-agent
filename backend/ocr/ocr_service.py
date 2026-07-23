"""
Lightweight OCR service using PyTesseract for Render Free Tier (512MB RAM).
"""

from pathlib import Path
from PIL import Image
import pytesseract

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
    Extract text from screenshot using PIL & PyTesseract (Zero Heavy Torch Memory).
    """
    path = Path(image_path)
    if not path.exists():
        raise OCRProcessingError(f"Image file not found: {path}")

    try:
        logger.info("Extracting OCR text from screenshot: '%s'", path.name)
        image = Image.open(path)
        
        # Extract real text from screenshot using PyTesseract
        extracted_text = pytesseract.image_to_string(image).strip()

        if not extracted_text:
            return f"[Image uploaded: {path.name}]. No clear text could be automatically extracted from the screenshot."

        return extracted_text

    except Exception as e:
        logger.error("PyTesseract OCR failed: %s", str(e))
        return f"[Image uploaded: {path.name}]. Error reading image text."