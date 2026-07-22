"""
Conversation memory and user-preference domain models (Pydantic V2).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1, max_length=8000)
    agent_name: str | None = Field(
        default=None, description="Which specialist agent produced this message, if any."
    )


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: MessageRole
    content: str
    agent_name: str | None
    created_at: datetime


class ConversationCreate(BaseModel):
    user_identifier: str = Field(
        ..., min_length=1, max_length=200, description="Employee name, email, or session ID."
    )


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_identifier: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []


class UserPreferenceSet(BaseModel):
    user_identifier: str = Field(..., min_length=1, max_length=200)
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., max_length=2000)


class UserPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_identifier: str
    key: str
    value: str
    updated_at: datetime
