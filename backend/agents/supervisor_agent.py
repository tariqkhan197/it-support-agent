"""
Supervisor agent.

Classifies an incoming employee message into one of the 7 specialist
categories using a small, fast LLM call, with a keyword-based fallback if
the LLM is unavailable or returns something unparseable — routing must
never hard-fail the whole pipeline.
"""

import json
import re

from pydantic import BaseModel, Field, ValidationError

from backend.prompts.agent_prompts import SPECIALIST_DEFINITIONS, SUPERVISOR_ROUTING_PROMPT
from backend.utils.exceptions import AgentRoutingError, LLMProviderError
from backend.utils.llm_client import LLMClient, LLMMessage
from backend.utils.logger import get_logger

logger = get_logger(__name__)

VALID_CATEGORIES = tuple(SPECIALIST_DEFINITIONS.keys())

# Fallback keyword map used only if the LLM classification call fails outright.
_KEYWORD_FALLBACK: dict[str, tuple[str, ...]] = {
    "printer": ("printer", "print", "scanner", "scan"),
    "vpn": ("vpn", "remote access"),
    "networking": ("wifi", "wi-fi", "network", "internet", "dns", "ip address", "lan"),
    "email": ("outlook", "email", "mailbox", "inbox"),
    "security": ("password", "locked out", "lockout", "phishing", "virus", "malware", "mfa", "2fa"),
    "windows": ("slow", "freeze", "frozen", "blue screen", "bsod", "crash", "windows", "boot"),
}


class RoutingDecision(BaseModel):
    category: str = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = ""


class SupervisorAgent:
    """Routes each user message to the correct SpecialistAgent category."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def classify(self, user_message: str) -> RoutingDecision:
        messages = [
            LLMMessage(role="system", content=SUPERVISOR_ROUTING_PROMPT),
            LLMMessage(role="user", content=user_message),
        ]

        try:
            result = self.llm_client.invoke(messages, agent_name="supervisor")
            decision = self._parse_decision(result.content)
            logger.info(
                "Supervisor routed to '%s' (confidence=%.2f): %s",
                decision.category, decision.confidence, decision.reasoning,
            )
            return decision
        except (LLMProviderError, json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Supervisor LLM classification failed (%s); using keyword fallback", exc)
            return self._keyword_fallback(user_message)

    @staticmethod
    def _parse_decision(raw_content: str) -> RoutingDecision:
        text = raw_content.strip()
        text = re.sub(r"^```(json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(match.group(0) if match else text)

        decision = RoutingDecision.model_validate(data)
        if decision.category not in VALID_CATEGORIES:
            raise AgentRoutingError(
                f"Supervisor returned unknown category '{decision.category}'",
                details={"valid_categories": list(VALID_CATEGORIES)},
            )
        return decision

    @staticmethod
    def _keyword_fallback(user_message: str) -> RoutingDecision:
        lowered = user_message.lower()
        for category, keywords in _KEYWORD_FALLBACK.items():
            if any(keyword in lowered for keyword in keywords):
                return RoutingDecision(
                    category=category,
                    confidence=0.4,
                    reasoning="Matched by keyword fallback (LLM classification unavailable).",
                )
        return RoutingDecision(
            category="general",
            confidence=0.2,
            reasoning="No keyword match; defaulted to general IT agent.",
        )
