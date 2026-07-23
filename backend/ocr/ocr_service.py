"""
OCR service using EasyOCR (Pure Python dependency - works natively on Render/Cloud).
"""

from pathlib import Path
import easyocr
from PIL import Image

from backend.config.settings import get_settings
from backend.utils.exceptions import FileValidationError, OCRProcessingError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Initialize EasyOCR Reader once (English)
try:
    reader = easyocr.Reader(['en'], gpu=False)
except Exception as exc:
    logger.error("Failed to initialize EasyOCR reader: %s", exc)
    reader = None


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
    """Run EasyOCR on an image file and return the extracted text."""
    path = Path(image_path)
    if not path.exists():
        raise OCRProcessingError(f"Image file not found: {path}")

    if reader is None:
        return "OCR engine initialization failed on server."

    try:
        # EasyOCR extracts text directly from image path
        results = reader.readtext(str(path), detail=0)
        extracted_text = " ".join(results).strip()
        
        logger.info("EasyOCR extracted %d characters from '%s'", len(extracted_text), path.name)
        return extracted_text if extracted_text else "No visible text found in screenshot."

    except Exception as exc:
        logger.error("EasyOCR processing error on '%s': %s", path.name, exc)
        return f"Error extracting text from screenshot: {str(exc)}"