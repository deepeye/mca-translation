"""管理员 API 测试 — 角色守卫 + 用户列表 + 调整额度 + 查看交易。"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
async def _clean_admin_test_tables():
    """每个测试前清空 users / credit_transactions，避免固定测试用户名跨运行重复。"""
    from sqlalchemy import text
    from app.core.database import engine
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE credit_transactions, users RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture(autouse=True)
async def _reset_global_engine():
    """每个测试前后释放全局 engine 连接池，避免跨 event loop 复用 asyncpg 连接。"""
    from app.core.database import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _make_user(db, *, admin=False, balance=100, username=None):
    user = User(
        id=uuid.uuid4(),
        username=username or f"u_{uuid.uuid4().hex[:8]}",
        hashed_password=get_password_hash("pw"),
        credit_balance=balance,
        is_admin=admin,
    )
    db.add(user)
    await db.commit()
    return user


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(user_id)})}"}


@pytest.mark.asyncio
async def test_non_admin_gets_403(db: AsyncSession):
    user = await _make_user(db, admin=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/users", headers=_headers(user.id))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_lists_users(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="admin1")
    other = await _make_user(db, admin=False, balance=250, username="alice")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/users", headers=_headers(admin.id))
    assert resp.status_code == 200
    data = resp.json()
    usernames = [u["username"] for u in data]
    assert "admin1" in usernames and "alice" in usernames
    alice = next(u for u in data if u["username"] == "alice")
    assert alice["credit_balance"] == 250
    assert alice["is_admin"] is False


@pytest.mark.asyncio
async def test_admin_adjust_topup(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="admin2")
    target = await _make_user(db, balance=100, username="bob")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/admin/users/{target.id}/credits",
            headers=_headers(admin.id),
            json={"delta": 500, "reason": "季度充值"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"balance": 600}


@pytest.mark.asyncio
async def test_admin_adjust_revoke_clamps_at_zero(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="admin3")
    target = await _make_user(db, balance=100, username="carol")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/admin/users/{target.id}/credits",
            headers=_headers(admin.id),
            json={"delta": -300, "reason": "回收"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"balance": 0}


@pytest.mark.asyncio
async def test_admin_views_user_transactions(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="admin4")
    target = await _make_user(db, balance=1000, username="dave")
    from app.services.credits import credits_service
    await credits_service.deduct_for_translation(db, target.id, "你好", "en-GB", uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/admin/transactions?user_id={target.id}",
            headers=_headers(admin.id),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["delta"] == -2
