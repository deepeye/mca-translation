"""Create an admin user — dev default or custom credentials for production.

Examples:
  python scripts/seed_admin.py                                       # dev: admin / admin123
  python scripts/seed_admin.py --username pdmi --password 'Pdmi@2026'
"""
import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.core.database import async_session
from app.core.security import get_password_hash
from app.models.user import User


async def create_admin(username: str, password: str) -> None:
    async with async_session() as db:
        existing = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing:
            print(f"Admin user already exists: {username}")
            return
        user = User(
            id=uuid.uuid4(),
            username=username,
            hashed_password=get_password_hash(password),
            is_admin=True,
        )
        db.add(user)
        await db.commit()
        print(f"Admin user created: {username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--username", default="admin", help="admin username (default: admin)")
    parser.add_argument("--password", default="admin123", help="admin password (default: admin123)")
    args = parser.parse_args()
    asyncio.run(create_admin(args.username, args.password))


if __name__ == "__main__":
    main()
