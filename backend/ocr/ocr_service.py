"""
OCR service (Tesseract via pytesseract).

Extracts text from uploaded screenshots so error dialogs, BSOD stop codes,
and error dialog text can be read and diagnosed automatically.
Includes safe fallback for environments without Tesseract binary (e.g. Render Free Tier).
"""

from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError

from backend.config.settings import get_settings
from backend.utils.exceptions import FileValidationError, OCRProcessingError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

if hasattr(settings, "TESSERACT_CMD") and settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


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
    Run OCR on an image file and return the extracted text.
    If Tesseract binary is missing on server, returns a safe fallback message
    instead of crashing the request.
    """
    path = Path(image_path)
    if not path.exists():
        raise OCRProcessingError(f"Image file not found: {path}")

    try:
        image = Image.open(path)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise OCRProcessingError(f"'{path.name}' is not a valid, readable image file: {exc}") from exc

    try:
        # Grayscale conversion improves OCR accuracy
        text = pytesseract.image_to_string(image.convert("L"))
        cleaned = text.strip()
        logger.info("OCR extracted %d characters from '%s'", len(cleaned), path.name)
        return cleaned if cleaned else "[OCR Notice]: No text detected in image."
    
    except Exception as exc:  # Catch Tesseract missing / PATH error gracefully
        logger.warning("Tesseract OCR unavailable on host (%s): %s", path.name, exc)
        # Fallback text so downstream diagnosis pipeline continues safely
        return (
            "[OCR Notice]: Tesseract engine is not installed on this server environment. "
            "Screenshot uploaded successfully and queued for standard AI diagnosis."
        )