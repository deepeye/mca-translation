"""管理员 API 测试 — 角色守卫 + 用户列表 + 调整额度 + 查看交易。"""
import uuid
from datetime import datetime, timezone

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


@pytest.mark.asyncio
async def test_admin_create_user(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="create_admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/users",
            headers=_headers(admin.id),
            json={"username": "newuser", "password": "pass123", "is_admin": False},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["is_admin"] is False
    assert data["is_active"] is True
    assert data["credit_balance"] == 1000
    assert "id" in data


@pytest.mark.asyncio
async def test_admin_create_user_duplicate(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="dup_admin")
    await _make_user(db, username="existing_user")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/users",
            headers=_headers(admin.id),
            json={"username": "existing_user", "password": "pass123"},
        )
    assert resp.status_code == 409
    assert "用户名已存在" in resp.text


@pytest.mark.asyncio
async def test_admin_create_user_short_password(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="pw_admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/users",
            headers=_headers(admin.id),
            json={"username": "newuser2", "password": "ab", "is_admin": False},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_update_user(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="upd_admin")
    target = await _make_user(db, username="upd_target")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            f"/api/admin/users/{target.id}",
            headers=_headers(admin.id),
            json={"username": "updated_name", "is_admin": True},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "updated_name"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_admin_update_self_admin_fails(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="self_admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            f"/api/admin/users/{admin.id}",
            headers=_headers(admin.id),
            json={"is_admin": False},
        )
    assert resp.status_code == 409
    assert "不能移除自己的管理员权限" in resp.text


@pytest.mark.asyncio
async def test_admin_update_nonexistent_user(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="nonexist_admin")
    fake_id = uuid.uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            f"/api/admin/users/{fake_id}",
            headers=_headers(admin.id),
            json={"username": "ghost"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_delete_user(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="del_admin")
    target = await _make_user(db, username="del_target")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/admin/users/{target.id}",
            headers=_headers(admin.id),
        )
        assert resp.status_code == 204
        # 确认逻辑删除 — 用户不在列表中
        resp2 = await client.get("/api/admin/users", headers=_headers(admin.id))
        usernames = [u["username"] for u in resp2.json()]
        assert "del_target" not in usernames


@pytest.mark.asyncio
async def test_admin_delete_self_fails(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="self_del")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/admin/users/{admin.id}",
            headers=_headers(admin.id),
        )
    assert resp.status_code == 409
    assert "不能删除当前登录的管理员" in resp.text


@pytest.mark.asyncio
async def test_admin_toggle_status(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="tog_admin")
    target = await _make_user(db, username="tog_target")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 禁用
        resp = await client.patch(
            f"/api/admin/users/{target.id}/status",
            headers=_headers(admin.id),
            json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        # 启用
        resp2 = await client.patch(
            f"/api/admin/users/{target.id}/status",
            headers=_headers(admin.id),
            json={"is_active": True},
        )
        assert resp2.status_code == 200
        assert resp2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_admin_toggle_self_fails(db: AsyncSession):
    admin = await _make_user(db, admin=True, username="self_tog")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(
            f"/api/admin/users/{admin.id}/status",
            headers=_headers(admin.id),
            json={"is_active": False},
        )
    assert resp.status_code == 409
    assert "不能禁用当前登录的管理员" in resp.text


@pytest.mark.asyncio
async def test_login_disabled_user_returns_403(db: AsyncSession):
    from app.core.security import get_password_hash
    user = User(
        username="disabled_user",
        hashed_password=get_password_hash("pass123"),
        is_active=False,
    )
    db.add(user)
    await db.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "disabled_user", "password": "pass123"})
    assert resp.status_code == 403
    assert "账号已被禁用" in resp.text


@pytest.mark.asyncio
async def test_login_deleted_user_returns_401(db: AsyncSession):
    from app.core.security import get_password_hash
    user = User(
        username="deleted_user",
        hashed_password=get_password_hash("pass123"),
        deleted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "deleted_user", "password": "pass123"})
    assert resp.status_code == 401
