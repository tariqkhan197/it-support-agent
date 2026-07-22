"""
Prompt injection / input safety guardrail.

Applies lightweight, fast heuristic checks to user input BEFORE it is sent
to the LLM. This is a defense-in-depth layer, not a replacement for the
system-prompt hardening already present in every agent prompt.

Two things are checked:
    1. Injection patterns   — attempts to override instructions, extract
                               the system prompt, or make the model role-play
                               as an unrestricted system.
    2. Basic input hygiene   — length limits and control-character stripping.
"""

import re

from backend.utils.exceptions import PromptInjectionDetectedError
from backend.utils.logger import get_logger

logger = get_logger(__name__)

MAX_INPUT_LENGTH = 4000

# Compiled once at import time for speed. Case-insensitive.
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"(show|print|output)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+\w+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+are\s+)?(an?\s+)?(unrestricted|jailbroken|dan)\b", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+have\s+no|there\s+are\s+no)\s+(rules|restrictions|guidelines)", re.IGNORECASE),
    re.compile(r"\bsystem\s*:\s*", re.IGNORECASE),
    re.compile(r"</?(system|assistant|user)>", re.IGNORECASE),
    re.compile(r"new\s+instructions\s*:", re.IGNORECASE),
]

# Strip characters that have no place in a support message and are common
# in obfuscated injection attempts (zero-width chars, control chars).
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b\u200c\u200d\ufeff]")


def sanitize_input(raw_text: str) -> str:
    """Strip invisible/control characters and collapse excess whitespace."""
    cleaned = _CONTROL_CHAR_PATTERN.sub("", raw_text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def check_prompt_injection(raw_text: str) -> None:
    """
    Raise PromptInjectionDetectedError if the text matches a known
    injection pattern. Callers should sanitize_input() first.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(raw_text):
            logger.warning("Prompt injection pattern matched: %s", pattern.pattern)
            raise PromptInjectionDetectedError(
                "Your message could not be processed because it matched a pattern "
                "associated with prompt manipulation. Please rephrase your IT issue "
                "in plain language.",
                details={"matched_pattern": pattern.pattern},
            )


def validate_user_message(raw_text: str) -> str:
    """
    Full input pipeline for any text headed to an LLM: length check,
    sanitization, then injection screening. Returns the cleaned text.

    Raises:
        PromptInjectionDetectedError if the message is unsafe or too long.
    """
    if not raw_text or not raw_text.strip():
        raise PromptInjectionDetectedError("Message cannot be empty.")

    if len(raw_text) > MAX_INPUT_LENGTH:
        raise PromptInjectionDetectedError(
            f"Message is too long ({len(raw_text)} characters). "
            f"Please limit messages to {MAX_INPUT_LENGTH} characters."
        )

    cleaned = sanitize_input(raw_text)
    check_prompt_injection(cleaned)
    return cleaned
