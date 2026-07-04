"""promote_admin CLI 测试。"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.scripts.promote_admin import promote_admin


@pytest.mark.asyncio
async def test_promote_admin_sets_flag(db: AsyncSession, monkeypatch):
    """promote_admin 应将指定用户的 is_admin 置为 True。"""
    user = User(
        id=uuid.uuid4(),
        username=f"to_promote_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_admin=False,
    )
    db.add(user)
    await db.commit()

    # 让 promote_admin 使用当前测试 session
    async def _fake_session():
        yield db

    monkeypatch.setattr("app.scripts.promote_admin.get_session", _fake_session)
    await promote_admin(user.username)

    await db.refresh(user)
    assert user.is_admin is True


@pytest.mark.asyncio
async def test_promote_admin_unknown_user_raises(db: AsyncSession, monkeypatch):
    async def _fake_session():
        yield db

    monkeypatch.setattr("app.scripts.promote_admin.get_session", _fake_session)
    with pytest.raises(ValueError, match="User not found"):
        await promote_admin("nonexistent_user_xyz")
