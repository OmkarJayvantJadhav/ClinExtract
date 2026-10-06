import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.database import get_db
from src.core.rate_limit import SlidingWindowLimiter
from src.db.models.user import User
from src.schemas.auth import UserLogin, UserResponse, PasswordChangeRequest
from src.utils.security import (
    verify_password, create_access_token, burn_password_check, password_policy_error, get_password_hash,
)
from src.api.deps import get_current_user
from src.services.audit import log_audit_event

router = APIRouter()

RESOURCE_USER = "User"
login_limiter = SlidingWindowLimiter(settings.LOGIN_RATE_LIMIT_PER_MINUTE, 60.0)

def _client_ip(request: Request) -> str:
    # Behind the bundled reverse proxy the real client address is in X-Real-IP (set by Caddy,
    # overwriting anything the client sent). Never trust it when the API is exposed directly.
    if settings.TRUST_PROXY_HEADERS:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"

def set_auth_cookies(response: Response, user: User) -> None:
    access_token = create_access_token(subject=str(user.id), role=user.role.value, token_version=user.token_version or 0)
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    # HttpOnly cookie for the JWT
    response.set_cookie(
        key="access_token", value=access_token, httponly=True,
        secure=settings.cookie_secure, samesite="strict", max_age=max_age,
    )
    # Readable cookie for the double-submit CSRF token
    response.set_cookie(
        key="clinextract_csrf", value=secrets.token_urlsafe(32), httponly=False,
        secure=settings.cookie_secure, samesite="strict", max_age=max_age,
    )

def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", httponly=True, secure=settings.cookie_secure, samesite="strict")
    response.delete_cookie("clinextract_csrf", secure=settings.cookie_secure, samesite="strict")

@router.post("/login", response_model=UserResponse)
async def login(
    login_data: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> Any:
    ip = _client_ip(request)
    if not login_limiter.allow(ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts. Try again in a minute.")

    stmt = select(User).where(User.username == login_data.username).with_for_update()
    user = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if not user:
        burn_password_check(login_data.password)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    if user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked after repeated failed logins. Try again later or contact an administrator.",
        )

    if not verify_password(login_data.password, user.password_hash):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        locked = user.failed_login_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS
        if locked:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            user.failed_login_count = 0
        await log_audit_event(
            db, action="USER_ACCOUNT_LOCKED" if locked else "USER_LOGIN_FAILED", resource_type=RESOURCE_USER,
            resource_id=str(user.id), after_state={"ip": ip},
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

    user.failed_login_count = 0
    user.locked_until = None
    await log_audit_event(db, action="USER_LOGIN", resource_type=RESOURCE_USER, resource_id=str(user.id), user_id=user.id, after_state={"ip": ip})
    await db.commit()

    set_auth_cookies(response, user)
    return user

@router.post("/logout")
async def logout(response: Response):
    # No authentication required: an expired session must still be able to clear its cookies.
    # (Clearing cookies is harmless, and SameSite=strict prevents cross-site triggering.)
    clear_auth_cookies(response)
    return {"detail": "Successfully logged out"}

@router.post("/logout-all")
async def logout_everywhere(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke every session of the current user, on all devices."""
    current_user.token_version = (current_user.token_version or 0) + 1
    await log_audit_event(db, action="USER_SESSIONS_REVOKED", resource_type=RESOURCE_USER, resource_id=str(current_user.id), user_id=current_user.id)
    await db.commit()
    clear_auth_cookies(response)
    return {"detail": "All sessions revoked"}

@router.post("/change-password", response_model=UserResponse)
async def change_password(
    body: PasswordChangeRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if body.new_password == body.current_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="New password must differ from the current password")
    problem = password_policy_error(body.new_password, current_user.username)
    if problem:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=problem)

    current_user.password_hash = get_password_hash(body.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)
    # Revoke other sessions, then issue a fresh cookie for this one
    current_user.token_version = (current_user.token_version or 0) + 1
    await log_audit_event(db, action="USER_PASSWORD_CHANGED", resource_type=RESOURCE_USER, resource_id=str(current_user.id), user_id=current_user.id)
    await db.commit()
    await db.refresh(current_user)
    set_auth_cookies(response, current_user)
    return current_user

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get current logged in user"""
    return current_user
