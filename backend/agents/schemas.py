"""
Structured agent output schema.

Every specialist agent is instructed to respond with JSON matching this
schema, enforcing the required reasoning pattern: analyze -> identify
causes -> choose approach -> explain why -> solve. Parsing the LLM output
into this Pydantic model guarantees the frontend and ticket-escalation
logic always receive a predictable shape.
"""

from pydantic import BaseModel, Field

from backend.models.ticket import TicketPriority


class TroubleshootingResponse(BaseModel):
    """The required reasoning + solution structure for every specialist agent reply."""

    analysis: str = Field(..., description="Plain-language summary of what the issue appears to be.")
    possible_causes: list[str] = Field(
        ..., min_length=1, description="Ranked list of likely root causes, most likely first."
    )
    chosen_approach: str = Field(..., description="The troubleshooting path selected to try first.")
    approach_rationale: str = Field(..., description="Why this approach was chosen over the alternatives.")
    solution_steps: list[str] = Field(
        default_factory=list, description="Concrete, numbered steps the employee should follow."
    )
    follow_up_question: str | None = Field(
        default=None, description="A clarifying question to ask, if more information is needed first."
    )
    requires_ticket: bool = Field(
        default=False, description="True if this issue cannot be self-resolved and needs an engineer."
    )
    suggested_ticket_priority: TicketPriority | None = Field(
        default=None, description="Priority to use if a ticket is created."
    )
    used_knowledge_base: bool = Field(
        default=False, description="True if the answer was grounded in retrieved company documents."
    )


RESPONSE_FORMAT_INSTRUCTIONS = """
Respond with ONLY a single valid JSON object — no markdown fences, no prose
before or after it — matching exactly this shape:

{
  "analysis": "<plain-language summary of the issue>",
  "possible_causes": ["<cause 1>", "<cause 2>", "..."],
  "chosen_approach": "<the troubleshooting path you are recommending first>",
  "approach_rationale": "<why you chose this path over other options>",
  "solution_steps": ["<step 1>", "<step 2>", "..."],
  "follow_up_question": "<a clarifying question, or null if none is needed>",
  "requires_ticket": <true or false>,
  "suggested_ticket_priority": "<low | medium | high | critical, or null>",
  "used_knowledge_base": <true or false>
}

Rules:
- Always reason internally through: analyze the issue, identify possible
  causes, choose the best troubleshooting path, explain why, THEN give steps.
- If you are missing critical information, set "follow_up_question" and give
  your best preliminary "solution_steps" anyway (can be an empty list).
- Set "requires_ticket" to true only if the issue cannot reasonably be
  self-resolved by the employee (e.g. hardware failure, account lockout
  needing admin action, security incident).
- Keep language simple — the reader is a non-technical employee.
""".strip()
