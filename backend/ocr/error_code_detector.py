"""
Error code detector.

Scans OCR-extracted text for recognizable error code patterns:
    - Windows hex codes:     0x8007000D, 0X000000EF
    - BSOD stop code names:  CRITICAL_PROCESS_DIED, IRQL_NOT_LESS_OR_EQUAL
    - VPN/dial-up errors:    "Error 809", "Error 691"
    - Generic "Error N" patterns used by many Windows subsystems
"""

import re

from backend.models.ocr import DetectedErrorCode
from backend.ocr.error_code_knowledge import lookup_error_code

_HEX_CODE_PATTERN = re.compile(r"0x[0-9A-Fa-f]{8}", re.IGNORECASE)
_BSOD_STOP_CODE_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){1,6}\b")
_GENERIC_ERROR_NUMBER_PATTERN = re.compile(r"\berror\s*(?:code)?\s*[:#]?\s*(\d{3,4})\b", re.IGNORECASE)

# Words that structurally match the BSOD pattern (ALL_CAPS_WITH_UNDERSCORES)
# but are not actually stop codes, to avoid false positives from OCR noise.
_BSOD_ALLOWLIST = {
    "CRITICAL_PROCESS_DIED",
    "IRQL_NOT_LESS_OR_EQUAL",
    "PAGE_FAULT_IN_NONPAGED_AREA",
    "DPC_WATCHDOG_VIOLATION",
    "UNMOUNTABLE_BOOT_VOLUME",
    "SYSTEM_SERVICE_EXCEPTION",
    "KERNEL_SECURITY_CHECK_FAILURE",
    "MEMORY_MANAGEMENT",
    "KMODE_EXCEPTION_NOT_HANDLED",
    "DRIVER_IRQL_NOT_LESS_OR_EQUAL",
}


def detect_error_codes(text: str) -> list[DetectedErrorCode]:
    """Find all recognizable error codes in the given text, enriched with known documentation."""
    found: dict[str, DetectedErrorCode] = {}

    for match in _HEX_CODE_PATTERN.finditer(text):
        code = match.group(0).upper()
        if code not in found:
            found[code] = _build_detected_code(code, "windows_hex")

    for match in _BSOD_STOP_CODE_PATTERN.finditer(text):
        candidate = match.group(0).upper()
        if candidate in _BSOD_ALLOWLIST and candidate not in found:
            found[candidate] = _build_detected_code(candidate, "bsod_stop_code")

    for match in _GENERIC_ERROR_NUMBER_PATTERN.finditer(text):
        number = match.group(1)
        code = f"ERROR {number}"
        if code not in found:
            found[code] = _build_detected_code(code, "generic_error_number")

    return list(found.values())


def _build_detected_code(code: str, fallback_type: str) -> DetectedErrorCode:
    known = lookup_error_code(code)
    if known:
        return DetectedErrorCode(
            code=code,
            code_type=known["code_type"],
            known_description=known["description"],
            known_causes=known["causes"],
        )
    return DetectedErrorCode(code=code, code_type=fallback_type, known_description=None, known_causes=[])
