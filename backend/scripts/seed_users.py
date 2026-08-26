import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.database import async_session_maker
from src.db.models.user import User, UserRole
from src.utils.security import get_password_hash
from sqlalchemy import select

async def seed():
    roles_to_seed = [
        ("admin", UserRole.ADMIN, os.getenv("ADMIN_SEED_PASSWORD", "devpass_admin")),
        ("reviewer", UserRole.REVIEWER, os.getenv("REVIEWER_SEED_PASSWORD", "devpass_reviewer")),
        ("reviewer1", UserRole.REVIEWER, os.getenv("REVIEWER_SEED_PASSWORD", "devpass_reviewer")),
        ("reviewer2", UserRole.REVIEWER, os.getenv("REVIEWER_SEED_PASSWORD", "password123")),
        ("operator", UserRole.OPERATOR, os.getenv("OPERATOR_SEED_PASSWORD", "devpass_operator")),
        ("viewer", UserRole.VIEWER, os.getenv("VIEWER_SEED_PASSWORD", "devpass_viewer")),
    ]

    async with async_session_maker() as session:
        for username, role, password in roles_to_seed:
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if not existing_user:
                new_user = User(
                    username=username,
                    password_hash=get_password_hash(password),
                    role=role,
                    is_active=True
                )
                session.add(new_user)
                print(f"Created '{username}' user")
            else:
                existing_user.password_hash = get_password_hash(password)
                print(f"User '{username}' already exists. Updated password.")

        await session.commit()
        print("Seed complete.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())
