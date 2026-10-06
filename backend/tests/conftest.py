import os
os.environ["APP_ENV"] = "testing"
# Point the suite at a dedicated database to keep test data out of your dev database:
#   TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/clinextract_test
# The database must exist; its tables are created automatically.
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import pytest
import asyncio
import sys
from fastapi.testclient import TestClient

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.main import app
from src.core.database import async_session_maker, engine
from src.db.models import Base
from src.db.models.user import User, UserRole
from src.utils.security import get_password_hash
from sqlalchemy import select

TEST_USERS = [
    ("admin", UserRole.ADMIN, "devpass_admin"),
    ("reviewer", UserRole.REVIEWER, "devpass_reviewer"),
    ("operator", UserRole.OPERATOR, "devpass_operator"),
    ("viewer", UserRole.VIEWER, "devpass_viewer"),
]

@pytest.fixture(scope="session", autouse=True)
async def _create_test_schema():
    """Create tables and the users the suite logs in as, when running against a dedicated test database."""
    if os.environ.get("TEST_DATABASE_URL"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session_maker() as session:
            for username, role, password in TEST_USERS:
                exists = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
                if not exists:
                    session.add(User(username=username, password_hash=get_password_hash(password), role=role, is_active=True))
                else:
                    # Start every run from a known state (earlier runs may have locked/changed these)
                    exists.password_hash = get_password_hash(password)
                    exists.failed_login_count = 0
                    exists.locked_until = None
                    exists.is_active = True
                    exists.role = role
            await session.commit()
    yield

@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    # The suite logs in far more often than the per-IP production limit allows
    from src.api.routes.auth import login_limiter
    login_limiter.reset()
    yield

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
async def db_session():
    async with async_session_maker() as session:
        yield session

@pytest.fixture
async def user(db_session):
    stmt = select(User).where(User.username == "admin")
    result = await db_session.execute(stmt)
    u = result.scalar_one_or_none()
    if not u:
        u = User(username="admin", password_hash=get_password_hash("devpass_admin"), role=UserRole.ADMIN, is_active=True)
        db_session.add(u)
        await db_session.commit()
    return u
