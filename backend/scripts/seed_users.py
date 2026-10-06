"""
Seed development users.

    python scripts/seed_users.py            # create missing users, leave existing passwords alone
    python scripts/seed_users.py --reset    # also reset existing users' passwords
    python scripts/seed_users.py --reset --user admin   # only the listed user(s)

Passwords come from *_SEED_PASSWORD environment variables; the dev defaults are only for local use.
"""
import argparse
import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.config import settings
from src.core.database import async_session_maker
from src.db.models.user import User, UserRole
from src.utils.security import get_password_hash
from sqlalchemy import select

async def seed(reset_passwords: bool, only_users: list[str] | None = None):
    reviewer_pw = os.getenv("REVIEWER_SEED_PASSWORD", "devpass_reviewer")
    roles_to_seed = [
        ("admin", UserRole.ADMIN, os.getenv("ADMIN_SEED_PASSWORD", "devpass_admin")),
        ("reviewer", UserRole.REVIEWER, reviewer_pw),
        ("reviewer1", UserRole.REVIEWER, reviewer_pw),
        ("reviewer2", UserRole.REVIEWER, reviewer_pw),
        ("operator", UserRole.OPERATOR, os.getenv("OPERATOR_SEED_PASSWORD", "devpass_operator")),
        ("viewer", UserRole.VIEWER, os.getenv("VIEWER_SEED_PASSWORD", "devpass_viewer")),
    ]

    if only_users:
        roles_to_seed = [r for r in roles_to_seed if r[0] in only_users]
        if not roles_to_seed:
            raise SystemExit(f"No seed users match {only_users}")

    if settings.APP_ENV == "production" and any(pw.startswith("devpass_") for _, _, pw in roles_to_seed):
        raise SystemExit("Refusing to seed default dev passwords with APP_ENV=production; set *_SEED_PASSWORD variables.")

    async with async_session_maker() as session:
        for username, role, password in roles_to_seed:
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if not existing_user:
                session.add(User(
                    username=username,
                    password_hash=get_password_hash(password),
                    role=role,
                    is_active=True
                ))
                print(f"Created '{username}' user")
            elif reset_passwords:
                existing_user.password_hash = get_password_hash(password)
                print(f"User '{username}' already exists. Password reset.")
            else:
                print(f"User '{username}' already exists. Left unchanged.")

        await session.commit()
        print("Seed complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="reset passwords of users that already exist")
    parser.add_argument("--user", action="append", help="only seed/reset this username (repeatable)")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed(args.reset, args.user))
