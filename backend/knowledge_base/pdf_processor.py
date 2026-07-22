"""
PDF text extraction (PyMuPDF).
"""

from pathlib import Path

import fitz  # PyMuPDF

from backend.utils.exceptions import DocumentProcessingError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PageText:
    """Extracted text for a single PDF page."""

    def __init__(self, page_number: int, text: str) -> None:
        self.page_number = page_number  # 1-indexed for human-readable citations
        self.text = text


def extract_pages(pdf_path: str | Path) -> list[PageText]:
    """
    Extract text from every page of a PDF.

    Raises DocumentProcessingError if the file can't be opened or parsed
    (e.g. corrupted, password-protected, or not actually a PDF).
    """
    path = Path(pdf_path)
    if not path.exists():
        raise DocumentProcessingError(f"PDF file not found: {path}")

    try:
        doc = fitz.open(path)
    except Exception as exc:  # noqa: BLE001
        raise DocumentProcessingError(f"Failed to open PDF '{path.name}': {exc}") from exc

    if doc.is_encrypted:
        doc.close()
        raise DocumentProcessingError(f"PDF '{path.name}' is password-protected and cannot be processed.")

    pages: list[PageText] = []
    try:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            text = page.get_text("text").strip()
            pages.append(PageText(page_number=page_index + 1, text=text))
    except Exception as exc:  # noqa: BLE001
        raise DocumentProcessingError(f"Failed to extract text from '{path.name}': {exc}") from exc
    finally:
        doc.close()

    non_empty_pages = sum(1 for p in pages if p.text)
    if non_empty_pages == 0:
        logger.warning(
            "PDF '%s' produced no extractable text on any of its %d pages "
            "(likely a scanned/image-only PDF — consider OCR ingestion instead).",
            path.name, len(pages),
        )

    logger.info("Extracted %d pages from '%s' (%d with text)", len(pages), path.name, non_empty_pages)
    return pages
