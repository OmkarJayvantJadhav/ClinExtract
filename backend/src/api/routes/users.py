import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.db.models.user import User, UserRole
from src.schemas.auth import UserResponse, UserCreateRequest, UserUpdateRequest, PasswordResetRequest
from src.api.deps import require_roles
from src.services.audit import log_audit_event
from src.utils.security import get_password_hash, password_policy_error

router = APIRouter()

RESOURCE_USER = "User"
admin_only = require_roles([UserRole.ADMIN])

async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.username))
    return result.scalars().all()

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    if (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")
    problem = password_policy_error(body.password, body.username)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    user = User(
        username=body.username, role=body.role, is_active=True,
        password_hash=get_password_hash(body.password),
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    await log_audit_event(
        db, action="USER_CREATED", resource_type=RESOURCE_USER, resource_id=str(user.id),
        user_id=current_user.id, after_state={"username": user.username, "role": user.role.value},
    )
    await db.commit()
    await db.refresh(user)
    return user

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    user = await _get_user_or_404(db, user_id)
    if user.id == current_user.id and (
        (body.role is not None and body.role != UserRole.ADMIN) or body.is_active is False
    ):
        raise HTTPException(status_code=400, detail="You cannot demote or deactivate your own account")

    before = {"role": user.role.value, "is_active": user.is_active}
    if body.role is not None and body.role != user.role:
        user.role = body.role
        user.token_version = (user.token_version or 0) + 1  # new permissions take effect immediately
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        if not body.is_active:
            user.token_version = (user.token_version or 0) + 1

    await log_audit_event(
        db, action="USER_UPDATED", resource_type=RESOURCE_USER, resource_id=str(user.id), user_id=current_user.id,
        before_state=before, after_state={"role": user.role.value, "is_active": user.is_active},
    )
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(
    user_id: uuid.UUID,
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    user = await _get_user_or_404(db, user_id)
    problem = password_policy_error(body.new_password, user.username)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    user.password_hash = get_password_hash(body.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.token_version = (user.token_version or 0) + 1
    user.failed_login_count = 0
    user.locked_until = None
    await log_audit_event(db, action="USER_PASSWORD_RESET", resource_type=RESOURCE_USER, resource_id=str(user.id), user_id=current_user.id)
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/{user_id}/unlock", response_model=UserResponse)
async def unlock_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    user = await _get_user_or_404(db, user_id)
    user.failed_login_count = 0
    user.locked_until = None
    await log_audit_event(db, action="USER_UNLOCKED", resource_type=RESOURCE_USER, resource_id=str(user.id), user_id=current_user.id)
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/{user_id}/revoke-sessions", response_model=UserResponse)
async def revoke_sessions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    user = await _get_user_or_404(db, user_id)
    user.token_version = (user.token_version or 0) + 1
    await log_audit_event(db, action="USER_SESSIONS_REVOKED", resource_type=RESOURCE_USER, resource_id=str(user.id), user_id=current_user.id)
    await db.commit()
    await db.refresh(user)
    return user
