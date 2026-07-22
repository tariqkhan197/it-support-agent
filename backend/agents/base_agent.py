"""
Base specialist agent.

All 7 specialist agents (Windows, Networking, Printer, VPN, Email,
Security, General) share identical orchestration logic — build the
prompt, call the LLM, parse structured JSON, retry once on malformed
output. Only their category and system prompt differ, so that shared
logic lives here once (no duplicated code across agents).
"""

import json
import re

from pydantic import ValidationError

from backend.agents.schemas import RESPONSE_FORMAT_INSTRUCTIONS, TroubleshootingResponse
from backend.prompts.agent_prompts import BASE_AGENT_SYSTEM_PROMPT_TEMPLATE, SPECIALIST_DEFINITIONS
from backend.utils.exceptions import LLMProviderError
from backend.utils.llm_client import LLMClient, LLMMessage
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw_text: str) -> dict:
    """
    LLMs occasionally wrap JSON in markdown fences or add stray text.
    Pull out the first {...} block and parse it defensively.
    """
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()

    match = _JSON_BLOCK_PATTERN.search(text)
    candidate = match.group(0) if match else text
    return json.loads(candidate)


class SpecialistAgent:
    """
    Base class for a category specialist. Subclasses just set `category`.

    category must be a key in SPECIALIST_DEFINITIONS (backend/prompts/agent_prompts.py).
    """

    category: str = "general"

    def __init__(self, llm_client: LLMClient) -> None:
        if self.category not in SPECIALIST_DEFINITIONS:
            raise ValueError(f"Unknown specialist category: {self.category}")
        self.llm_client = llm_client
        self._definition = SPECIALIST_DEFINITIONS[self.category]
        self.system_prompt = BASE_AGENT_SYSTEM_PROMPT_TEMPLATE.format(
            display_name=self._definition["display_name"],
            specialty_description=self._definition["specialty_description"],
            response_format_instructions=RESPONSE_FORMAT_INSTRUCTIONS,
        )

    def handle(
        self,
        *,
        user_message: str,
        conversation_history: list[LLMMessage] | None = None,
        knowledge_base_context: str | None = None,
        user_preferences: dict[str, str] | None = None,
    ) -> TroubleshootingResponse:
        """
        Run the reasoning pipeline for one turn: build messages -> call LLM
        -> parse -> validate -> (retry once on failure) -> return.
        """
        messages = self._build_messages(
            user_message=user_message,
            conversation_history=conversation_history or [],
            knowledge_base_context=knowledge_base_context,
            user_preferences=user_preferences or {},
        )

        result = self.llm_client.invoke(messages, agent_name=self.category)

        try:
            return self._parse_response(result.content)
        except (json.JSONDecodeError, ValidationError) as first_error:
            logger.warning(
                "[%s agent] Malformed structured output, retrying once: %s",
                self.category, first_error,
            )
            retry_messages = messages + [
                LLMMessage(
                    role="user",
                    content=(
                        "Your last reply was not valid JSON matching the required schema. "
                        "Respond again with ONLY the valid JSON object, nothing else."
                    ),
                )
            ]
            retry_result = self.llm_client.invoke(retry_messages, agent_name=f"{self.category}_retry")
            try:
                return self._parse_response(retry_result.content)
            except (json.JSONDecodeError, ValidationError) as second_error:
                raise LLMProviderError(
                    f"{self.category} agent failed to produce valid structured output after retry",
                    details={"raw_output": retry_result.content[:500]},
                ) from second_error

    def _build_messages(
        self,
        *,
        user_message: str,
        conversation_history: list[LLMMessage],
        knowledge_base_context: str | None,
        user_preferences: dict[str, str],
    ) -> list[LLMMessage]:
        system_content = self.system_prompt

        if user_preferences:
            prefs_text = ", ".join(f"{k}: {v}" for k, v in user_preferences.items())
            system_content += f"\n\nKNOWN USER PREFERENCES: {prefs_text}"

        if knowledge_base_context:
            system_content += (
                f"\n\nKNOWLEDGE BASE CONTEXT (grounded company documentation):\n"
                f"{knowledge_base_context}"
            )

        messages = [LLMMessage(role="system", content=system_content)]
        messages.extend(conversation_history[-10:])  # cap history to keep prompts small
        messages.append(LLMMessage(role="user", content=user_message))
        return messages

    @staticmethod
    def _parse_response(raw_content: str) -> TroubleshootingResponse:
        data = _extract_json(raw_content)
        return TroubleshootingResponse.model_validate(data)
