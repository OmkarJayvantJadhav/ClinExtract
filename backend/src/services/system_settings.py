"""Runtime-editable system settings stored in the system_settings table."""
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.system_setting import SystemSetting

THRESHOLDS_KEY = "confidence_thresholds"

# Fractions (0..1). These match the validation engine's historical behaviour.
DEFAULT_THRESHOLDS = {
    "auto_accept": 0.90,         # overall confidence needed for auto-acceptance
    "review_recommended": 0.90,  # fields below this are "REVIEW_RECOMMENDED"
    "low_confidence": 0.70,      # fields below this are "LOW" and always force review
}

def validate_thresholds(values: dict) -> Optional[str]:
    auto, high, low = values["auto_accept"], values["review_recommended"], values["low_confidence"]
    if not all(isinstance(v, (int, float)) for v in (auto, high, low)):
        return "Thresholds must be numbers"
    if not (0.0 < low <= high <= 1.0):
        return "Require 0 < low_confidence <= review_recommended <= 1"
    if not (0.5 <= auto <= 1.0):
        return "auto_accept must be between 0.5 and 1.0"
    return None

async def get_thresholds(db: AsyncSession) -> dict:
    row = await db.get(SystemSetting, THRESHOLDS_KEY)
    values = dict(DEFAULT_THRESHOLDS)
    if row and isinstance(row.value, dict):
        values.update({k: float(v) for k, v in row.value.items() if k in DEFAULT_THRESHOLDS})
    return values

async def set_thresholds(db: AsyncSession, values: dict, user_id: Optional[uuid.UUID]) -> dict:
    """Validates and stages new thresholds (caller commits). Raises ValueError if invalid."""
    merged = await get_thresholds(db)
    merged.update({k: float(v) for k, v in values.items() if k in DEFAULT_THRESHOLDS and v is not None})
    problem = validate_thresholds(merged)
    if problem:
        raise ValueError(problem)
    row = await db.get(SystemSetting, THRESHOLDS_KEY)
    if row:
        row.value = merged
        row.updated_by = user_id
    else:
        db.add(SystemSetting(key=THRESHOLDS_KEY, value=merged, updated_by=user_id))
    return merged
