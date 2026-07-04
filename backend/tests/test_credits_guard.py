"""提交翻译/审校时的余额守卫 — 余额<=0 返回 402。"""
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


async def _zero_balance_user(db, username=None):
    user = User(
        id=uuid.uuid4(),
        username=username or f"broke_{uuid.uuid4().hex[:8]}",
        hashed_password=get_password_hash("pw"),
        credit_balance=0,
    )
    db.add(user)
    await db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}
    return user, headers


@pytest.mark.asyncio
async def test_create_job_blocked_when_zero_balance(db: AsyncSession):
    _, headers = await _zero_balance_user(db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/jobs", headers=headers, json={
            "source_text": "测试文本",
            "genre": "political",
            "strategy": "semantic_equivalence",
            "target_languages": ["en-GB"],
            "cultural_sphere": "western_english",
            "audience_type": "general_public",
        })
    assert resp.status_code == 402
    body = resp.json()
    assert body["detail"] == "INSUFFICIENT_CREDITS"
    assert body["balance"] == 0


@pytest.mark.asyncio
async def test_create_review_blocked_when_zero_balance(db: AsyncSession):
    _, headers = await _zero_balance_user(db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/reviews", headers=headers, json={
            "mode": "single",
            "translated_text": "Hello world",
            "target_language": "en-GB",
        })
    assert resp.status_code == 402
    assert resp.json()["detail"] == "INSUFFICIENT_CREDITS"


@pytest.mark.asyncio
async def test_create_job_allowed_with_positive_balance(db: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username=f"ok_{uuid.uuid4().hex[:8]}",
        hashed_password=get_password_hash("pw"),
        credit_balance=500,
    )
    db.add(user)
    await db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}
    transport = ASGITransport(app=app)
    from unittest.mock import patch
    with patch("app.api.jobs.run_translation.delay"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/jobs", headers=headers, json={
                "source_text": "测试",
                "genre": "political",
                "strategy": "semantic_equivalence",
                "target_languages": ["en-GB"],
            })
    assert resp.status_code == 201
