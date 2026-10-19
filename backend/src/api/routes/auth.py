import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.database import get_db
from src.core.rate_limit import DatabaseRateLimiter
from src.db.models.user import User, UserRole
from src.schemas.auth import UserLogin, UserResponse, PasswordChangeRequest
from src.utils.security import (
    verify_password, create_access_token, burn_password_check, password_policy_error, get_password_hash,
)
from src.api.deps import get_current_user
from src.services.audit import log_audit_event

router = APIRouter()

RESOURCE_USER = "User"
login_limiter = DatabaseRateLimiter(settings.LOGIN_RATE_LIMIT_PER_MINUTE, 60.0)

def _client_ip(request: Request) -> str:
    # Behind the bundled reverse proxy the real client address is in X-Real-IP (set by Caddy,
    # overwriting anything the client sent). Never trust it when the API is exposed directly.
    if settings.TRUST_PROXY_HEADERS:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"

def is_demo_account(user: User) -> bool:
    """Publicly shared demo account (never an admin, whatever DEMO_ACCOUNTS says)."""
    return user.username in settings.demo_usernames and user.role != UserRole.ADMIN

def _refuse_for_demo(user: User) -> None:
    if is_demo_account(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not available for shared demo accounts")

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

def _refused() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password. After repeated failures an account is locked for a while.",
    )

async def _record_wrong_password(db: AsyncSession, user: User, now: datetime, ip: str, action: str) -> bool:
    """
    Counts a wrong password (at login or when changing it) towards the lockout, audits it and
    commits. Returns whether the account is now locked.
    """
    # A shared demo account is never locked: anyone could otherwise lock everyone out.
    demo = is_demo_account(user)
    user.failed_login_count = 0 if demo else (user.failed_login_count or 0) + 1
    locked = not demo and user.failed_login_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS
    if locked:
        user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        user.failed_login_count = 0
    await log_audit_event(
        db, action="USER_ACCOUNT_LOCKED" if locked else action, resource_type=RESOURCE_USER,
        resource_id=str(user.id), after_state={"ip": ip},
    )
    await db.commit()
    return locked

@router.post("/login", response_model=UserResponse)
async def login(
    login_data: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> Any:
    ip = _client_ip(request)
    if not await login_limiter.allow(db, ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts. Try again in a minute.")

    stmt = select(User).where(User.username == login_data.username).with_for_update()
    user = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    # Every refusal below looks the same (status, message, a password check's work), so the
    # answer never tells which usernames exist or whether a guess for a locked or deactivated
    # account was right. Each one is audited.
    if not user:
        burn_password_check(login_data.password)
        await log_audit_event(
            db, action="USER_LOGIN_FAILED", resource_type=RESOURCE_USER, resource_id="unknown",
            after_state={"ip": ip, "reason": "unknown username", "username": login_data.username[:64]},
        )
        await db.commit()
        raise _refused()

    demo = is_demo_account(user)
    locked = bool(user.locked_until and user.locked_until > now and not demo)
    if locked or not user.is_active:
        burn_password_check(login_data.password)
        await log_audit_event(
            db, action="USER_LOGIN_BLOCKED", resource_type=RESOURCE_USER, resource_id=str(user.id),
            after_state={"ip": ip, "reason": "locked" if locked else "inactive"},
        )
        await db.commit()
        raise _refused()

    if not verify_password(login_data.password, user.password_hash):
        await _record_wrong_password(db, user, now, ip, "USER_LOGIN_FAILED")
        raise _refused()

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
    _refuse_for_demo(current_user)
    current_user.token_version = (current_user.token_version or 0) + 1
    await log_audit_event(db, action="USER_SESSIONS_REVOKED", resource_type=RESOURCE_USER, resource_id=str(current_user.id), user_id=current_user.id)
    await db.commit()
    clear_auth_cookies(response)
    return {"detail": "All sessions revoked"}

@router.post("/change-password", response_model=UserResponse)
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _refuse_for_demo(current_user)
    now = datetime.now(timezone.utc)
    await db.refresh(current_user, with_for_update=True)
    if current_user.locked_until and current_user.locked_until > now:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account temporarily locked after repeated wrong passwords.")
    if not verify_password(body.current_password, current_user.password_hash):
        # Guesses here count like failed logins: someone holding an unattended session must not
        # be able to try passwords without limit and then take the account over.
        locked = await _record_wrong_password(db, current_user, now, _client_ip(request), "USER_PASSWORD_CHANGE_FAILED")
        if locked:
            # End every session of the account, including the one being used to guess
            current_user.token_version = (current_user.token_version or 0) + 1
            await db.commit()
            clear_auth_cookies(response)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account temporarily locked after repeated wrong passwords.")
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

@router.get("/demo")
async def demo_accounts(db: AsyncSession = Depends(get_db)) -> Any:
    """Public: the shared demo accounts offered on the sign-in page (only on demo deployments)."""
    names = settings.demo_usernames
    if not names:
        return {"enabled": False, "accounts": []}
    stmt = select(User).where(User.username.in_(names), User.is_active.is_(True), User.role != UserRole.ADMIN)
    users = (await db.execute(stmt)).scalars().all()
    role_order = [UserRole.OPERATOR, UserRole.REVIEWER, UserRole.VIEWER]
    users = sorted(users, key=lambda u: (role_order.index(u.role) if u.role in role_order else 99, u.username))
    return {
        "enabled": bool(users),
        "accounts": [{"username": u.username, "role": u.role.value} for u in users],
        "password": settings.DEMO_PASSWORD if users else None,
    }
