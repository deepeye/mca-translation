"""Create a default admin user for development."""
import asyncio
import uuid

from app.core.database import async_session
from app.core.security import get_password_hash
from app.models.user import User


async def main():
    async with async_session() as db:
        from sqlalchemy import select
        existing = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if existing:
            print("Admin user already exists")
            return
        user = User(id=uuid.uuid4(), username="admin", hashed_password=get_password_hash("admin123"))
        db.add(user)
        await db.commit()
        print("Admin user created: admin / admin123")


if __name__ == "__main__":
    asyncio.run(main())
