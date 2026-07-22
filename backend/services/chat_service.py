"""
Chat service.

The orchestration layer between the API and the lower-level building
blocks: loads conversation memory, runs the LangGraph support workflow,
persists the turn, and automatically creates a ticket when the agent's
diagnosis indicates the issue needs an engineer (`requires_ticket=True`).
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.agents.schemas import TroubleshootingResponse
from backend.database.conversation_repository import ConversationRepository
from backend.database.ticket_repository import TicketRepository
from backend.knowledge_base.retrieval_service import RetrievalService
from backend.models.conversation import MessageCreate, MessageRole
from backend.models.ticket import TicketCategory, TicketCreate, TicketPriority
from backend.utils.exceptions import PromptInjectionDetectedError
from backend.utils.llm_client import LLMClient, LLMMessage
from backend.utils.logger import get_logger
from backend.workflows.support_workflow import run_support_workflow

logger = get_logger(__name__)

# The Supervisor's routing categories map 1:1 onto TicketCategory values,
# but we validate explicitly rather than assuming, since OCR/LLM output
# is external input.
_VALID_TICKET_CATEGORIES = {c.value for c in TicketCategory}


@dataclass
class ChatTurnResult:
    conversation_id: int
    category: str
    diagnosis: TroubleshootingResponse
    ticket_number: str | None
    retrieved_sources: list[dict]


class ChatService:
    def __init__(
        self,
        db: Session,
        llm_client: LLMClient,
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        self.db = db
        self.llm_client = llm_client
        self.retrieval_service = retrieval_service
        self.conversations = ConversationRepository(db)
        self.tickets = TicketRepository(db)

    def handle_message(
        self,
        *,
        user_identifier: str,
        user_message: str,
        requester_name: str | None = None,
        requester_email: str | None = None,
    ) -> ChatTurnResult:
        """
        Process one chat turn end-to-end:
            1. Load/continue the user's conversation
            2. Run the multi-agent workflow (guard -> route -> retrieve -> diagnose)
            3. Persist both the user and assistant messages
            4. Auto-create a ticket if the diagnosis requires one
        """
        conversation = self.conversations.get_or_create_active_conversation(user_identifier)

        history = self.conversations.get_recent_messages(conversation.id, limit=10)
        llm_history = [
            LLMMessage(role="user" if m.role == "user" else "assistant", content=m.content)
            for m in history
        ]
        preferences = self.conversations.get_preferences_dict(user_identifier)

        # Persist the user's message immediately so it's captured even if
        # the workflow later fails (guardrail rejection, LLM error, etc.).
        self.conversations.add_message(
            conversation.id, MessageCreate(role=MessageRole.USER, content=user_message)
        )

        result = run_support_workflow(
            llm_client=self.llm_client,
            user_message=user_message,
            user_identifier=user_identifier,
            conversation_history=llm_history,
            user_preferences=preferences,
            retrieval_service=self.retrieval_service,
        )

        if result.get("error"):
            # The guardrail blocked this input — record a system note, no ticket, no LLM cost.
            self.conversations.add_message(
                conversation.id,
                MessageCreate(role=MessageRole.SYSTEM, content=f"Message rejected: {result['error']}"),
            )
            raise PromptInjectionDetectedError(result["error"])

        diagnosis: TroubleshootingResponse = result["response"]
        category = result["category"]

        self.conversations.add_message(
            conversation.id,
            MessageCreate(
                role=MessageRole.ASSISTANT,
                content=self._format_diagnosis_as_text(diagnosis),
                agent_name=category,
            ),
        )

        ticket_number = None
        if diagnosis.requires_ticket:
            ticket_number = self._create_ticket_from_diagnosis(
                conversation_id=conversation.id,
                category=category,
                diagnosis=diagnosis,
                requester_name=requester_name or user_identifier,
                requester_email=requester_email,
            )

        return ChatTurnResult(
            conversation_id=conversation.id,
            category=category,
            diagnosis=diagnosis,
            ticket_number=ticket_number,
            retrieved_sources=result.get("retrieved_sources", []),
        )

    def _create_ticket_from_diagnosis(
        self,
        *,
        conversation_id: int,
        category: str,
        diagnosis: TroubleshootingResponse,
        requester_name: str,
        requester_email: str | None,
    ) -> str:
        safe_category = category if category in _VALID_TICKET_CATEGORIES else "general"
        priority = diagnosis.suggested_ticket_priority or TicketPriority.MEDIUM

        title = diagnosis.analysis[:150] if diagnosis.analysis else "IT support issue (auto-created)"
        description_parts = [
            f"Analysis: {diagnosis.analysis}",
            f"Possible causes: {', '.join(diagnosis.possible_causes)}",
            f"Attempted approach: {diagnosis.chosen_approach}",
        ]
        description = "\n".join(description_parts)[:5000]

        ticket = self.tickets.create_ticket(
            TicketCreate(
                title=title,
                description=description,
                category=TicketCategory(safe_category),
                priority=priority,
                requester_name=requester_name,
                requester_email=requester_email,
                source_conversation_id=conversation_id,
            )
        )
        logger.info("Auto-created ticket %s from conversation %d", ticket.ticket_number, conversation_id)
        return ticket.ticket_number

    @staticmethod
    def _format_diagnosis_as_text(diagnosis: TroubleshootingResponse) -> str:
        """Render the structured diagnosis as readable text for the conversation history."""
        lines = [diagnosis.analysis]
        if diagnosis.solution_steps:
            lines.append("\nSteps to try:")
            lines.extend(f"{i}. {step}" for i, step in enumerate(diagnosis.solution_steps, start=1))
        if diagnosis.follow_up_question:
            lines.append(f"\n{diagnosis.follow_up_question}")
        return "\n".join(lines)
