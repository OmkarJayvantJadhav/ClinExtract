from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from src.core.database import get_db
from src.db.models.user import User, UserRole
from src.schemas.auth import UserResponse
from src.api.deps import require_roles

router = APIRouter()

@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN]))
):
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.username))
    return result.scalars().all()
