"""
Chat API request/response schemas.
"""

from pydantic import BaseModel, ConfigDict, Field

from backend.agents.schemas import TroubleshootingResponse


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_identifier: str = Field(
        ..., min_length=1, max_length=200, description="Employee email or stable session ID."
    )
    message: str = Field(..., min_length=1, max_length=4000)
    requester_name: str | None = Field(default=None, max_length=120)
    requester_email: str | None = Field(default=None, max_length=200)


class ChatResponse(BaseModel):
    conversation_id: int
    category: str
    diagnosis: TroubleshootingResponse
    ticket_number: str | None
    retrieved_sources: list[dict]
