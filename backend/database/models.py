"""
SQLAlchemy ORM models (storage layer).

Kept deliberately separate from the Pydantic schemas in backend/models/ —
this file describes *how data is stored*, the Pydantic schemas describe
*how data is exchanged*. The repository layer translates between the two.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    """An IT support ticket, covering the full lifecycle from creation to closure."""

    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("ticket_number", name="uq_tickets_ticket_number"),
        CheckConstraint(
            "status IN ('open','in_progress','resolved','closed','reopened')",
            name="ck_tickets_status",
        ),
        CheckConstraint(
            "priority IN ('low','medium','high','critical')",
            name="ck_tickets_priority",
        ),
        CheckConstraint(
            "category IN ('windows','networking','printer','vpn','email','security','general')",
            name="ck_tickets_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_number: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="open")

    requester_name: Mapped[str] = mapped_column(String(120), nullable=False)
    requester_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assigned_engineer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    reopened_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source_conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    history: Mapped[list["TicketHistory"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TicketHistory.created_at"
    )


class TicketHistory(Base):
    """Audit trail of every status change / edit made to a ticket."""

    __tablename__ = "ticket_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)

    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(120), nullable=False, default="system")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="history")


class Conversation(Base):
    """A chat session between an employee and the AI assistant."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_identifier: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    """A single message within a conversation (user, assistant, or system)."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','system')", name="ck_messages_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class KnowledgeDocument(Base):
    """
    Metadata for an uploaded knowledge-base PDF.

    The actual text chunks and embeddings live in ChromaDB (see
    backend/knowledge_base/vector_store.py) — this table exists so the
    admin panel can list/search/delete documents by human-readable
    metadata without querying the vector store directly, and so deleting
    a document here can cascade to deleting its vectors by document_id.
    """

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    uploaded_by: Mapped[str] = mapped_column(String(120), nullable=False, default="admin")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class UserPreference(Base):
    """Key/value store of remembered user preferences (e.g. preferred OS, default printer)."""

    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_identifier", "key", name="uq_user_preferences_user_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_identifier: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
