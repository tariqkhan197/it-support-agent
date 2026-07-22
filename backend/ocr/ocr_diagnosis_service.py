"""
OCR diagnosis service.

Full pipeline for an uploaded screenshot:
    extract text -> detect error codes -> route to the right specialist
    (via the Supervisor) -> get a structured diagnosis grounded in any
    known error-code documentation.
"""

from pathlib import Path

from backend.agents.email_agent import EmailAgent
from backend.agents.general_agent import GeneralAgent
from backend.agents.networking_agent import NetworkingAgent
from backend.agents.printer_agent import PrinterAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.supervisor_agent import SupervisorAgent
from backend.agents.vpn_agent import VPNAgent
from backend.agents.windows_agent import WindowsAgent
from backend.models.ocr import OCRAnalysisResult
from backend.ocr.error_code_detector import detect_error_codes
from backend.ocr.ocr_service import extract_text_from_image, validate_image_upload
from backend.utils.exceptions import OCRProcessingError
from backend.utils.llm_client import LLMClient
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Codes with a code_type recognized here map directly to a specialist,
# skipping a separate LLM routing call when the code itself is unambiguous.
_CODE_TYPE_TO_CATEGORY = {
    "vpn_error": "vpn",
    "printer_error": "printer",
    "bsod_stop_code": "windows",
}


class OCRDiagnosisService:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client
        self.supervisor = SupervisorAgent(llm_client)
        self._specialists = {
            "windows": WindowsAgent(llm_client),
            "networking": NetworkingAgent(llm_client),
            "printer": PrinterAgent(llm_client),
            "vpn": VPNAgent(llm_client),
            "email": EmailAgent(llm_client),
            "security": SecurityAgent(llm_client),
            "general": GeneralAgent(llm_client),
        }

    def analyze_screenshot(
        self,
        *,
        image_path: str | Path,
        original_filename: str,
        file_size_bytes: int,
        user_message: str | None = None,
    ) -> OCRAnalysisResult:
        """
        Run the full screenshot-diagnosis pipeline and return a structured
        result: extracted text, detected error codes, routed category, and
        a full TroubleshootingResponse diagnosis.
        """
        validate_image_upload(original_filename, file_size_bytes)
        extracted_text = extract_text_from_image(image_path)

        if not extracted_text:
            raise OCRProcessingError(
                f"No text could be extracted from '{original_filename}'. "
                "Try a clearer screenshot with visible error text."
            )

        detected_codes = detect_error_codes(extracted_text)
        category = self._determine_category(extracted_text, detected_codes)

        prompt_message = self._build_diagnosis_prompt(
            extracted_text=extracted_text,
            detected_codes=detected_codes,
            user_message=user_message,
        )

        agent = self._specialists[category]
        diagnosis = agent.handle(user_message=prompt_message)

        logger.info(
            "OCR diagnosis complete for '%s': category=%s, codes=%d",
            original_filename, category, len(detected_codes),
        )

        return OCRAnalysisResult(
            raw_extracted_text=extracted_text,
            detected_error_codes=detected_codes,
            routed_category=category,
            diagnosis=diagnosis,
        )

    def _determine_category(self, extracted_text: str, detected_codes: list) -> str:
        """
        Prefer an unambiguous category implied by a detected error code's
        type; otherwise fall back to the Supervisor's LLM classification.
        """
        for code in detected_codes:
            if code.code_type in _CODE_TYPE_TO_CATEGORY:
                return _CODE_TYPE_TO_CATEGORY[code.code_type]

        decision = self.supervisor.classify(extracted_text[:2000])
        return decision.category

    @staticmethod
    def _build_diagnosis_prompt(
        *, extracted_text: str, detected_codes: list, user_message: str | None
    ) -> str:
        parts = ["An employee uploaded a screenshot of an error. Here is the OCR-extracted text:"]
        parts.append(f'"""\n{extracted_text[:3000]}\n"""')

        if detected_codes:
            parts.append("\nDetected error code(s):")
            for code in detected_codes:
                line = f"- {code.code}"
                if code.known_description:
                    line += f": {code.known_description}"
                    if code.known_causes:
                        line += f" (documented causes: {', '.join(code.known_causes)})"
                parts.append(line)

        if user_message:
            parts.append(f'\nThe employee also said: "{user_message}"')

        parts.append(
            "\nDiagnose this issue and provide step-by-step troubleshooting, "
            "following your required reasoning process."
        )
        return "\n".join(parts)
