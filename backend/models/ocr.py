"""
OCR domain models (Pydantic V2).
"""

from pydantic import BaseModel, Field

from backend.agents.schemas import TroubleshootingResponse


class DetectedErrorCode(BaseModel):
    """An error code pattern found in OCR-extracted text, with any known documentation."""

    code: str
    code_type: str = Field(..., description="e.g. 'windows_hex', 'bsod_stop_code', 'vpn_error', 'printer_error'")
    known_description: str | None = None
    known_causes: list[str] = Field(default_factory=list)


class OCRAnalysisResult(BaseModel):
    """Full result of analyzing an uploaded screenshot."""

    raw_extracted_text: str
    detected_error_codes: list[DetectedErrorCode]
    routed_category: str
    diagnosis: TroubleshootingResponse
