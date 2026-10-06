from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings as app_settings
from src.core.database import get_db
from src.db.models.user import User, UserRole
from src.api.deps import get_current_user, require_roles
from src.services.audit import log_audit_event
from src.services.system_settings import get_thresholds, set_thresholds

router = APIRouter()

class ThresholdsUpdate(BaseModel):
    auto_accept: float | None = Field(None, ge=0, le=1)
    review_recommended: float | None = Field(None, ge=0, le=1)
    low_confidence: float | None = Field(None, ge=0, le=1)

@router.get("")
async def read_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current runtime settings (thresholds are 0..1 fractions)."""
    return {
        "confidence_thresholds": await get_thresholds(db),
        "document_retention_days": app_settings.DOCUMENT_RETENTION_DAYS,
        "encryption_at_rest": bool(app_settings.DOCUMENT_ENCRYPTION_KEY),
        "password_min_length": app_settings.PASSWORD_MIN_LENGTH,
    }

@router.put("/confidence-thresholds")
async def update_thresholds(
    body: ThresholdsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
):
    """Update confidence thresholds (admin only). Applies to documents processed afterwards."""
    before = await get_thresholds(db)
    try:
        after = await set_thresholds(db, body.model_dump(), current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await log_audit_event(db, action="SETTINGS_UPDATED", resource_type="SystemSetting", resource_id="confidence_thresholds",
                          user_id=current_user.id, before_state=before, after_state=after)
    await db.commit()
    return {"confidence_thresholds": after}
