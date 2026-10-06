from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from src.core.config import settings

ph = PasswordHasher()

# Verified against when the username does not exist, so a failed login takes the same
# time whether or not the account exists (prevents username enumeration by timing).
_DUMMY_HASH = ph.hash("dummy-password-for-timing-equalisation")

def get_password_hash(password: str) -> str:
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def burn_password_check(plain_password: str) -> None:
    verify_password(plain_password, _DUMMY_HASH)

def password_policy_error(password: str, username: str | None = None) -> str | None:
    """Returns a human-readable reason the password is unacceptable, or None if it is fine."""
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
    if password.strip() != password:
        return "Password must not start or end with whitespace"
    if username and username.lower() in password.lower():
        return "Password must not contain the username"
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if classes < 3:
        return "Password must mix at least three of: lowercase, uppercase, digits, symbols"
    return None

def create_access_token(subject: str, role: str, token_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "role": role, "ver": token_version}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
