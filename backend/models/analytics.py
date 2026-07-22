"""
Analytics API response schema.
"""

from pydantic import BaseModel


class TicketAnalyticsResponse(BaseModel):
    total_tickets: int
    open_tickets: int
    closed_tickets: int
    critical_tickets: int
    tickets_created_today: int
    average_resolution_time_hours: float | None
    tickets_by_status: dict[str, int]
    tickets_by_category: dict[str, int]
