from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base

class LoginAttempt(Base):
    """One login attempt per row, keyed by client address, for rate limiting across API processes."""
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_key: Mapped[str] = mapped_column(String(64))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_login_attempts_client_key_attempted_at", "client_key", "attempted_at"),)
