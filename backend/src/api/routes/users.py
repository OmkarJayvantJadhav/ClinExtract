from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from src.core.database import get_db
from src.db.models.user import User, UserRole
from src.schemas.auth import UserResponse
from src.api.deps import require_roles, get_current_user

router = APIRouter()

@router.get("/admin-only", response_model=List[UserResponse])
async def list_users_admin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN]))
):
    stmt = select(User)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/reviewer-plus", response_model=List[UserResponse])
async def list_users_reviewer(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER]))
):
    stmt = select(User)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/operator-plus", response_model=List[UserResponse])
async def list_users_operator(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER, UserRole.OPERATOR]))
):
    stmt = select(User)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/viewer-plus", response_model=List[UserResponse])
async def list_users_viewer(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(User)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/dummy-mutation")
async def dummy_mutation(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER, UserRole.OPERATOR]))
):
    return {"status": "success"}
