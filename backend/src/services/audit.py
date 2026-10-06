import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.audit_log import AuditLog

# Canonical resource_type values. The audit API filters on these, so always use the constants.
RESOURCE_DOCUMENT = "Document"
RESOURCE_EXTRACTED_FIELD = "ExtractedField"

def _coerce_uuid(value: Any) -> Optional[uuid.UUID]:
    """Correlation IDs may arrive as arbitrary client-supplied strings; only store valid UUIDs."""
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None

async def log_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str,
    user_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[Any] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
):
    audit_log = AuditLog(
        id=uuid.uuid4(),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        correlation_id=_coerce_uuid(correlation_id),
        before_state=before_state,
        after_state=after_state,
    )
    db.add(audit_log)
