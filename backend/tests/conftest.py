import os
os.environ["APP_ENV"] = "testing"

import pytest
import asyncio
import sys
from fastapi.testclient import TestClient
from src.main import app

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

from src.core.database import async_session_maker
from src.db.models.user import User, UserRole
from src.utils.security import get_password_hash
from sqlalchemy import select

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
