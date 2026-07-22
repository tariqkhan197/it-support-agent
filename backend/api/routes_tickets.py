"""
Ticket management routes.

Public-ish endpoints (create/read) are usable by the employee-facing chat
UI; edit/assign/status-change/delete/export/analytics are admin-only.
"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.auth_utils import get_current_admin
from backend.api.rate_limiter import check_rate_limit
from backend.database.session import get_db
from backend.database.ticket_repository import TicketRepository
from backend.models.analytics import TicketAnalyticsResponse
from backend.models.ticket import (
    TicketCategory,
    TicketCreate,
    TicketPriority,
    TicketResponse,
    TicketStatus,
    TicketStatusChange,
    TicketUpdate,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.post("", response_model=TicketResponse, dependencies=[Depends(check_rate_limit)])
async def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketResponse:
    """Manually create a ticket (the chat endpoint also auto-creates tickets when needed)."""
    ticket = TicketRepository(db).create_ticket(payload)
    return TicketResponse.model_validate(ticket)


@router.get("", dependencies=[Depends(check_rate_limit)])
async def list_tickets(
    db: Session = Depends(get_db),
    status: TicketStatus | None = None,
    category: TicketCategory | None = None,
    priority: TicketPriority | None = None,
    assigned_engineer: str | None = None,
    search_text: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List/search/filter tickets. Returns a page of results plus the total matching count."""
    from backend.models.ticket import TicketFilter

    filters = TicketFilter(
        status=status,
        category=category,
        priority=priority,
        assigned_engineer=assigned_engineer,
        search_text=search_text,
        limit=limit,
        offset=offset,
    )
    tickets, total = TicketRepository(db).list_tickets(filters)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "tickets": [TicketResponse.model_validate(t) for t in tickets],
    }


@router.get("/analytics", response_model=TicketAnalyticsResponse)
async def get_ticket_analytics(
    db: Session = Depends(get_db), _admin: str = Depends(get_current_admin)
) -> TicketAnalyticsResponse:
    """Dashboard analytics: counts by status/category, resolution time, today's volume. Admin only."""
    repo = TicketRepository(db)
    by_status = repo.count_by_status()
    by_priority = repo.count_by_priority()
    return TicketAnalyticsResponse(
        total_tickets=sum(by_status.values()),
        open_tickets=by_status.get("open", 0) + by_status.get("in_progress", 0) + by_status.get("reopened", 0),
        closed_tickets=by_status.get("closed", 0),
        critical_tickets=by_priority.get("critical", 0),
        tickets_created_today=repo.tickets_created_today(),
        average_resolution_time_hours=repo.average_resolution_time_hours(),
        tickets_by_status=by_status,
        tickets_by_category=repo.count_by_category(),
    )


@router.get("/export", dependencies=[Depends(get_current_admin)])
async def export_tickets_csv(db: Session = Depends(get_db)) -> StreamingResponse:
    """Export all tickets as a downloadable CSV file. Admin only."""
    from backend.models.ticket import TicketFilter

    tickets, _ = TicketRepository(db).list_tickets(TicketFilter(limit=500))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ticket_number", "title", "category", "priority", "status",
        "requester_name", "requester_email", "assigned_engineer",
        "created_at", "resolved_at", "closed_at",
    ])
    for t in tickets:
        writer.writerow([
            t.ticket_number, t.title, t.category, t.priority, t.status,
            t.requester_name, t.requester_email or "", t.assigned_engineer or "",
            t.created_at.isoformat(), t.resolved_at.isoformat() if t.resolved_at else "",
            t.closed_at.isoformat() if t.closed_at else "",
        ])
    buffer.seek(0)

    filename = f"tickets_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketResponse:
    ticket = TicketRepository(db).get_by_id(ticket_id)
    return TicketResponse.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> TicketResponse:
    """Edit ticket fields. Admin only."""
    ticket = TicketRepository(db).update_ticket(ticket_id, payload)
    return TicketResponse.model_validate(ticket)


@router.post("/{ticket_id}/assign", response_model=TicketResponse)
async def assign_ticket(
    ticket_id: int,
    engineer_name: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> TicketResponse:
    """Assign a ticket to an engineer. Admin only."""
    ticket = TicketRepository(db).assign_ticket(ticket_id, engineer_name)
    return TicketResponse.model_validate(ticket)


@router.post("/{ticket_id}/status", response_model=TicketResponse)
async def change_ticket_status(
    ticket_id: int,
    payload: TicketStatusChange,
    db: Session = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> TicketResponse:
    """Transition a ticket's status (open -> in_progress -> resolved -> closed -> reopened). Admin only."""
    ticket = TicketRepository(db).change_status(
        ticket_id, payload.new_status, note=payload.resolution_notes, changed_by=payload.changed_by
    )
    return TicketResponse.model_validate(ticket)


@router.delete("/{ticket_id}")
async def delete_ticket(
    ticket_id: int, db: Session = Depends(get_db), _admin: str = Depends(get_current_admin)
) -> dict:
    """Permanently delete a ticket. Admin only."""
    TicketRepository(db).delete_ticket(ticket_id)
    return {"deleted": True, "ticket_id": ticket_id}
