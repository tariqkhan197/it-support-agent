"""
OCR routes — analyze an uploaded screenshot of an error.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from backend.api.dependencies import get_llm_client
from backend.api.rate_limiter import check_rate_limit
from backend.models.ocr import OCRAnalysisResult
from backend.ocr.ocr_diagnosis_service import OCRDiagnosisService
from backend.utils.llm_client import GroqLLMClient

router = APIRouter(prefix="/ocr", tags=["OCR"])


@router.post("/analyze", response_model=OCRAnalysisResult, dependencies=[Depends(check_rate_limit)])
async def analyze_screenshot(
    file: UploadFile = File(...),
    user_message: str | None = Form(default=None),
    llm_client: GroqLLMClient = Depends(get_llm_client),
) -> OCRAnalysisResult:
    """
    Upload a screenshot of an error dialog / blue screen. Extracts the
    text, detects known Windows/VPN/printer error codes, and returns a
    full diagnosis from the appropriate specialist agent.
    """
    contents = await file.read()
    suffix = Path(file.filename).suffix or ".png"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        service = OCRDiagnosisService(llm_client)
        return service.analyze_screenshot(
            image_path=tmp_path,
            original_filename=file.filename,
            file_size_bytes=len(contents),
            user_message=user_message,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
