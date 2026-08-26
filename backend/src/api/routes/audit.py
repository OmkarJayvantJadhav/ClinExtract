from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Dict, Any, Optional
import uuid

from src.core.database import get_db
from src.db.models.audit_log import AuditLog
from src.api.routes.auth import get_current_user
from src.schemas.auth import UserResponse

router = APIRouter()

@router.get("", response_model=Dict[str, Any])
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
    document_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100)
):
    # Enforce RBAC: Only Admin/Supervisor can see global audit logs
    if current_user.role not in ["ADMIN", "SUPERVISOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view audit logs"
        )
        
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at))
    
    if document_id:
        stmt = stmt.where(AuditLog.resource_id == document_id, AuditLog.resource_type == "document")
            
    if user_id:
        try:
            user_uuid = uuid.UUID(user_id)
            stmt = stmt.where(AuditLog.user_id == user_uuid)
        except ValueError:
            return {"items": [], "total": 0, "page": page, "size": size}
            
    if action:
        stmt = stmt.where(AuditLog.action == action)
        
    # Count total
    from sqlalchemy import func
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
            "document_id": r.resource_id if r.resource_type == "document" else None,
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
