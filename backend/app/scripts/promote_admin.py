"""提升用户为管理员的 CLI 脚本。

用法：python -m app.scripts.promote_admin <username>
"""
import argparse
import asyncio
import sys

from sqlalchemy import select

from app.models.user import User


async def get_session():
    """默认使用应用配置的数据库 session；测试时通过 monkeypatch 替换。"""
    from app.core.database import async_session
    async with async_session() as session:
        yield session


async def promote_admin(username: str) -> None:
    async for db in get_session():
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User not found: {username}")
        user.is_admin = True
        await db.commit()
        print(f"Promoted {username} to admin.")
        return


def main():
    parser = argparse.ArgumentParser(description="Promote a user to admin role")
    parser.add_argument("username", help="Username to promote")
    args = parser.parse_args()
    try:
        asyncio.run(promote_admin(args.username))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
