"""信用分用户端 API 测试。"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
async def _reset_global_engine():
    """每个测试前后释放全局 engine 连接池，避免跨 event loop 复用 asyncpg 连接。"""
    from app.core.database import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _auth_client(db, username=None, balance=1000):
    user = User(
        id=uuid.uuid4(),
        username=username or f"api_user_{uuid.uuid4().hex[:8]}",
        hashed_password=get_password_hash("pw"),
        credit_balance=balance,
    )
    db.add(user)
    await db.commit()
    token = create_access_token(data={"sub": str(user.id)})
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return user, client, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_balance(db: AsyncSession):
    user, client, headers = await _auth_client(db, balance=42)
    resp = await client.get("/api/credits/balance", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] == 42
    assert body["is_admin"] is False


@pytest.mark.asyncio
async def test_get_balance_unauth(db: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/credits/balance")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_transactions(db: AsyncSession):
    user, client, headers = await _auth_client(db, balance=100)
    # 制造一笔扣款
    from app.services.credits import credits_service
    await credits_service.deduct_for_translation(db, user.id, "你好", "en-GB", uuid.uuid4())
    resp = await client.get("/api/credits/transactions?limit=10", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["delta"] == -2
    assert data[0]["tx_type"] == "consume"


@pytest.mark.asyncio
async def test_get_trend_default_7_days(db: AsyncSession):
    user, client, headers = await _auth_client(db, balance=1000)
    from app.services.credits import credits_service
    await credits_service.deduct_for_translation(db, user.id, "你好世界", "en-GB", uuid.uuid4())
    resp = await client.get("/api/credits/trend?days=7", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7
    assert data[-1]["consumed"] == 4
