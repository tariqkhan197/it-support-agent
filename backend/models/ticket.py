"""
Ticket domain models (Pydantic V2).

These are the schemas used at the API boundary and by the agents/workflows —
distinct from the SQLAlchemy ORM classes in database/models.py, which
represent storage. Keeping them separate (schema vs. ORM) follows the
repository pattern and avoids leaking database internals into the API.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TicketCategory(str, Enum):
    """Maps 1:1 to the specialist agents in the multi-agent system."""

    WINDOWS = "windows"
    NETWORKING = "networking"
    PRINTER = "printer"
    VPN = "vpn"
    EMAIL = "email"
    SECURITY = "security"
    GENERAL = "general"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


# Status transitions allowed by the ticket lifecycle. Enforced by the
# repository so the system can never move a ticket into an invalid state
# (e.g. closing a ticket that was never resolved).
ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.OPEN, TicketStatus.CLOSED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.REOPENED},
    TicketStatus.CLOSED: {TicketStatus.REOPENED},
    TicketStatus.REOPENED: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED},
}


class TicketCreate(BaseModel):
    """Input schema for creating a new ticket — typically from the chat agent or a user form."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=5, max_length=5000)
    category: TicketCategory
    priority: TicketPriority = TicketPriority.MEDIUM
    requester_name: str = Field(..., min_length=1, max_length=120)
    requester_email: str | None = Field(default=None, max_length=200)
    source_conversation_id: int | None = None

    @field_validator("requester_email")
    @classmethod
    def _basic_email_shape(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("requester_email must look like a valid email address")
        return value


class TicketUpdate(BaseModel):
    """Input schema for admin edits. All fields optional — only provided fields are changed."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=5, max_length=5000)
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    assigned_engineer: str | None = Field(default=None, max_length=120)
    resolution_notes: str | None = Field(default=None, max_length=5000)


class TicketStatusChange(BaseModel):
    """Input schema for an explicit status transition (open -> in_progress -> resolved -> closed, etc.)."""

    new_status: TicketStatus
    resolution_notes: str | None = Field(default=None, max_length=5000)
    changed_by: str = Field(default="system", max_length=120)


class TicketResponse(BaseModel):
    """Output schema returned by the API and shown in the admin dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    title: str
    description: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    requester_name: str
    requester_email: str | None
    assigned_engineer: str | None
    resolution_notes: str | None
    reopened_count: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None


class TicketFilter(BaseModel):
    """Query parameters accepted by the ticket list/search endpoint."""

    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    assigned_engineer: str | None = None
    search_text: str | None = Field(default=None, max_length=200)
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
