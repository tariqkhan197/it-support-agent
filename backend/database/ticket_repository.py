"""
Ticket repository.

Encapsulates every database operation involving tickets so that the API
layer, agents, and Streamlit admin panel never write raw SQL/ORM queries
themselves — they all go through this class. This keeps the ticket
lifecycle rules (valid status transitions, timestamps, history logging)
enforced in exactly one place.
"""

from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.database.models import Ticket, TicketHistory
from backend.models.ticket import (
    ALLOWED_TRANSITIONS,
    TicketCreate,
    TicketFilter,
    TicketStatus,
    TicketUpdate,
)
from backend.utils.exceptions import TicketNotFoundError, TicketValidationError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TicketRepository:
    """All ticket persistence logic lives here. One instance per DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    def create_ticket(self, data: TicketCreate) -> Ticket:
        """
        Create a new ticket.

        Ticket numbers are generated as TCK-000001, TCK-000002, ... derived
        from the auto-incrementing primary key, so they are guaranteed
        unique without a separate sequence table.
        """
        ticket = Ticket(
            ticket_number="PENDING",  # placeholder until we have the id
            title=data.title,
            description=data.description,
            category=data.category.value,
            priority=data.priority.value,
            status=TicketStatus.OPEN.value,
            requester_name=data.requester_name,
            requester_email=data.requester_email,
            source_conversation_id=data.source_conversation_id,
        )
        self.db.add(ticket)
        self.db.flush()  # populates ticket.id without committing

        ticket.ticket_number = f"TCK-{ticket.id:06d}"

        self.db.add(
            TicketHistory(
                ticket_id=ticket.id,
                from_status=None,
                to_status=TicketStatus.OPEN.value,
                note="Ticket created",
                changed_by=data.requester_name,
            )
        )
        self.db.commit()
        self.db.refresh(ticket)

        logger.info("Created ticket %s (category=%s, priority=%s)", ticket.ticket_number, ticket.category, ticket.priority)
        return ticket

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def get_by_id(self, ticket_id: int) -> Ticket:
        ticket = self.db.get(Ticket, ticket_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket with id {ticket_id} not found")
        return ticket

    def get_by_ticket_number(self, ticket_number: str) -> Ticket:
        ticket = self.db.query(Ticket).filter(Ticket.ticket_number == ticket_number).first()
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_number} not found")
        return ticket

    def list_tickets(self, filters: TicketFilter) -> tuple[list[Ticket], int]:
        """Returns (page_of_tickets, total_matching_count) applying all filters."""
        query = self.db.query(Ticket)

        if filters.status is not None:
            query = query.filter(Ticket.status == filters.status.value)
        if filters.category is not None:
            query = query.filter(Ticket.category == filters.category.value)
        if filters.priority is not None:
            query = query.filter(Ticket.priority == filters.priority.value)
        if filters.assigned_engineer is not None:
            query = query.filter(Ticket.assigned_engineer == filters.assigned_engineer)
        if filters.created_after is not None:
            query = query.filter(Ticket.created_at >= filters.created_after)
        if filters.created_before is not None:
            query = query.filter(Ticket.created_at <= filters.created_before)
        if filters.search_text:
            like_pattern = f"%{filters.search_text}%"
            query = query.filter(
                or_(
                    Ticket.title.ilike(like_pattern),
                    Ticket.description.ilike(like_pattern),
                    Ticket.ticket_number.ilike(like_pattern),
                    Ticket.requester_name.ilike(like_pattern),
                )
            )

        total = query.count()
        results = (
            query.order_by(Ticket.created_at.desc())
            .offset(filters.offset)
            .limit(filters.limit)
            .all()
        )
        return results, total

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update_ticket(self, ticket_id: int, data: TicketUpdate) -> Ticket:
        ticket = self.get_by_id(ticket_id)

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if field in ("category", "priority") and value is not None:
                value = value.value  # enum -> str
            setattr(ticket, field, value)

        self.db.commit()
        self.db.refresh(ticket)
        logger.info("Updated ticket %s: %s", ticket.ticket_number, list(update_fields.keys()))
        return ticket

    def assign_ticket(self, ticket_id: int, engineer_name: str) -> Ticket:
        ticket = self.get_by_id(ticket_id)
        ticket.assigned_engineer = engineer_name
        if ticket.status == TicketStatus.OPEN.value:
            ticket.status = TicketStatus.IN_PROGRESS.value
        self.db.commit()
        self.db.refresh(ticket)
        logger.info("Assigned ticket %s to %s", ticket.ticket_number, engineer_name)
        return ticket

    def change_status(
        self,
        ticket_id: int,
        new_status: TicketStatus,
        *,
        note: str | None = None,
        changed_by: str = "system",
    ) -> Ticket:
        """
        Transition a ticket's status, enforcing the allowed-transition graph
        and stamping resolved_at/closed_at/reopened_count as appropriate.
        """
        ticket = self.get_by_id(ticket_id)
        current_status = TicketStatus(ticket.status)

        if new_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
            raise TicketValidationError(
                f"Cannot transition ticket {ticket.ticket_number} from "
                f"'{current_status.value}' to '{new_status.value}'",
                details={"from": current_status.value, "to": new_status.value},
            )

        now = datetime.now(timezone.utc)
        old_status = ticket.status
        ticket.status = new_status.value

        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = now
            if note:
                ticket.resolution_notes = note
        elif new_status == TicketStatus.CLOSED:
            ticket.closed_at = now
        elif new_status == TicketStatus.REOPENED:
            ticket.reopened_count += 1
            ticket.resolved_at = None
            ticket.closed_at = None

        self.db.add(
            TicketHistory(
                ticket_id=ticket.id,
                from_status=old_status,
                to_status=new_status.value,
                note=note,
                changed_by=changed_by,
            )
        )
        self.db.commit()
        self.db.refresh(ticket)
        logger.info("Ticket %s: %s -> %s", ticket.ticket_number, old_status, new_status.value)
        return ticket

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    def delete_ticket(self, ticket_id: int) -> None:
        ticket = self.get_by_id(ticket_id)
        self.db.delete(ticket)
        self.db.commit()
        logger.warning("Deleted ticket %s", ticket.ticket_number)

    # ------------------------------------------------------------------ #
    # Analytics (used by the dashboard in a later phase)
    # ------------------------------------------------------------------ #
    def count_by_status(self) -> dict[str, int]:
        rows = self.db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
        return {status: count for status, count in rows}

    def count_by_category(self) -> dict[str, int]:
        rows = self.db.query(Ticket.category, func.count(Ticket.id)).group_by(Ticket.category).all()
        return {category: count for category, count in rows}

    def count_by_priority(self) -> dict[str, int]:
        rows = self.db.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
        return {priority: count for priority, count in rows}

    def average_resolution_time_hours(self) -> float | None:
        rows = (
            self.db.query(Ticket.created_at, Ticket.resolved_at)
            .filter(Ticket.resolved_at.isnot(None))
            .all()
        )
        if not rows:
            return None
        total_seconds = sum((resolved - created).total_seconds() for created, resolved in rows)
        return round((total_seconds / len(rows)) / 3600, 2)

    def tickets_created_today(self) -> int:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return self.db.query(Ticket).filter(Ticket.created_at >= today_start).count()
