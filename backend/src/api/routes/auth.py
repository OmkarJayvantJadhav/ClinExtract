from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any

from src.core.database import get_db
from src.db.models.user import User
from src.schemas.auth import UserLogin, UserResponse
from src.utils.security import verify_password, create_access_token
from src.api.deps import get_current_user

import secrets
from src.core.config import settings

router = APIRouter()

@router.post("/login", response_model=UserResponse)
async def login(
    login_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Find user
    stmt = select(User).where(User.username == login_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
        )

    # Generate JWT
    access_token = create_access_token(subject=str(user.id), role=user.role.value)
    
    # Generate CSRF token
    csrf_token = secrets.token_urlsafe(32)

    is_production = settings.APP_ENV == "production"

    # Set HttpOnly Cookie for JWT
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_production,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    
    # Set non-HttpOnly Cookie for CSRF
    response.set_cookie(
        key="clinextract_csrf",
        value=csrf_token,
        httponly=False,
        secure=is_production,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return user

@router.post("/logout")
async def logout(response: Response):
    # No authentication required: an expired session must still be able to clear its cookies.
    # (Clearing cookies is harmless, and SameSite=strict prevents cross-site triggering.)
    is_production = settings.APP_ENV == "production"
    response.delete_cookie("access_token", httponly=True, secure=is_production, samesite="strict")
    response.delete_cookie("clinextract_csrf", secure=is_production, samesite="strict")
    return {"detail": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get current logged in user"""
    return current_user
