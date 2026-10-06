from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, or_, and_
from typing import Dict, Any, Optional
import uuid

from src.core.database import get_db
from src.db.models.audit_log import AuditLog
from src.db.models.user import User, UserRole
from src.api.deps import get_current_user
from src.services.audit import RESOURCE_DOCUMENT, RESOURCE_EXTRACTED_FIELD

router = APIRouter()

def _document_id_of(record: AuditLog) -> Optional[str]:
    if record.resource_type == RESOURCE_DOCUMENT:
        return record.resource_id
    if record.resource_type == RESOURCE_EXTRACTED_FIELD and isinstance(record.before_state, dict):
        return record.before_state.get("document_id")
    return None

@router.get("", response_model=Dict[str, Any])
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    document_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100)
):
    # The global audit log is admin-only; any signed-in user may see a single document's history.
    if not document_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to view audit logs")

    stmt = select(AuditLog).order_by(desc(AuditLog.created_at))
    
    if document_id:
        # Document events plus field corrections made on that document
        stmt = stmt.where(or_(
            and_(AuditLog.resource_type == RESOURCE_DOCUMENT, AuditLog.resource_id == document_id),
            and_(AuditLog.resource_type == RESOURCE_EXTRACTED_FIELD,
                 AuditLog.before_state["document_id"].as_string() == document_id),
        ))
            
    if user_id:
        try:
            user_uuid = uuid.UUID(user_id)
            stmt = stmt.where(AuditLog.user_id == user_uuid)
        except ValueError:
            return {"items": [], "total": 0, "page": page, "size": size}
            
    if action:
        stmt = stmt.where(AuditLog.action == action)
        
    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt)
    
    # Pagination
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    items = []
    for r in records:
        items.append({
            "id": str(r.id),
            "document_id": _document_id_of(r),
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "user_id": str(r.user_id) if r.user_id else None,
            "action": r.action,
            "changes": {"before": r.before_state, "after": r.after_state},
            "created_at": r.created_at.isoformat(),
            "correlation_id": str(r.correlation_id) if r.correlation_id else None
        })
        
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size
    }
