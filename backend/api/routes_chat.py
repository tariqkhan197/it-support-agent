"""
Chat routes.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.dependencies import get_llm_client, get_retrieval_service
from backend.api.rate_limiter import check_rate_limit
from backend.database.session import get_db
from backend.knowledge_base.retrieval_service import RetrievalService
from backend.models.chat import ChatRequest, ChatResponse
from backend.services.chat_service import ChatService
from backend.utils.llm_client import GroqLLMClient

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, dependencies=[Depends(check_rate_limit)])
async def send_chat_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    llm_client: GroqLLMClient = Depends(get_llm_client),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> ChatResponse:
    """
    Send a message to the AI IT Support Assistant.

    Runs input validation, prompt-injection screening, category routing,
    knowledge-base retrieval, and specialist diagnosis. Automatically
    creates a support ticket if the issue can't be self-resolved.
    """
    service = ChatService(db, llm_client, retrieval_service)
    result = service.handle_message(
        user_identifier=payload.user_identifier,
        user_message=payload.message,
        requester_name=payload.requester_name,
        requester_email=payload.requester_email,
    )
    return ChatResponse(
        conversation_id=result.conversation_id,
        category=result.category,
        diagnosis=result.diagnosis,
        ticket_number=result.ticket_number,
        retrieved_sources=result.retrieved_sources,
    )
