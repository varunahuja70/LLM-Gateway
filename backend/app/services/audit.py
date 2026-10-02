import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent
from app.logging_setup import redact_data


async def log_audit_event(
    session: AsyncSession,
    action: str,
    actor_type: str = "owner",
    actor_id: str | uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Record an audit trail event without secret data."""
    scrubbed_details = redact_data(details) if details else None

    event = AuditEvent(
        action=action,
        actor_type=actor_type,
        actor_id=str(actor_id) if actor_id else None,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        details=scrubbed_details,
    )
    session.add(event)
    await session.flush()
    return event
