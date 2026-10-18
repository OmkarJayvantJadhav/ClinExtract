import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.login_attempt import LoginAttempt

class DatabaseRateLimiter:
    """
    Sliding-window rate limiter backed by the database, so the limit holds across every API
    process and replica (an in-memory limiter is multiplied by the number of processes).
    """

    # Rows older than this are deleted now and then; they no longer affect any window.
    RETENTION = timedelta(hours=1)

    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)

    async def allow(self, db: AsyncSession, key: str) -> bool:
        """
        Records an attempt for `key` and returns whether it is within the limit. Commits on its
        own, so attempts count even when the request fails afterwards (e.g. unknown username).
        """
        now = datetime.now(timezone.utc)
        key = key[:64]
        recent = await db.scalar(
            select(func.count()).select_from(LoginAttempt)
            .where(LoginAttempt.client_key == key, LoginAttempt.attempted_at > now - self.window)
        )
        if recent >= self.limit:
            return False
        db.add(LoginAttempt(client_key=key, attempted_at=now))
        if random.random() < 0.01:
            await db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < now - self.RETENTION))
        await db.commit()
        return True
