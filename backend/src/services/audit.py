import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.audit_log import AuditLog

async def log_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str,
    user_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[uuid.UUID] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
):
    audit_log = AuditLog(
        id=uuid.uuid4(),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        correlation_id=correlation_id,
        before_state=before_state,
        after_state=after_state,
    )
    db.add(audit_log)
