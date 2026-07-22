"""
OCR service (Tesseract via pytesseract).

Extracts text from uploaded screenshots so error dialogs, BSOD stop codes,
and error dialog text can be read and diagnosed automatically.
"""

from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError

from backend.config.settings import get_settings
from backend.utils.exceptions import FileValidationError, OCRProcessingError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

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

    Raises OCRProcessingError if the file isn't a valid/readable image or
    if Tesseract itself fails.
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
        # Grayscale conversion improves OCR accuracy on UI screenshots/dialogs.
        text = pytesseract.image_to_string(image.convert("L"))
    except pytesseract.TesseractError as exc:
        raise OCRProcessingError(f"Tesseract failed to process '{path.name}': {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise OCRProcessingError(f"Unexpected OCR failure on '{path.name}': {exc}") from exc

    cleaned = text.strip()
    logger.info("OCR extracted %d characters from '%s'", len(cleaned), path.name)
    return cleaned
