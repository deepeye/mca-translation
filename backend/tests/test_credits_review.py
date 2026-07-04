"""审校管线信用分扣款/退还测试。"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.credit import CreditTransaction, TxType
from app.models.user import User


@pytest.fixture(autouse=True)
async def _reset_global_engine():
    """每个测试前后释放全局 engine 连接池，避免跨 event loop 复用 asyncpg 连接。"""
    from app.core.database import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _auth_user(db, balance=1000):
    user = User(
        id=uuid.uuid4(),
        username=f"rev_{uuid.uuid4().hex[:8]}",
        hashed_password=get_password_hash("pw"),
        credit_balance=balance,
    )
    db.add(user)
    await db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}
    return user, headers


async def _fake_review_success(*args, **kw):
    from app.schemas.review import ReviewResult
    return ReviewResult(
        review_id=uuid.uuid4(), mode="dual", overall_score=80,
        translated_text=kw.get("translated_text", ""), target_language="en-GB",
        audience_baseline="general_public", categories=[], summary="ok",
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_successful_review_deducts(db: AsyncSession):
    user, headers = await _auth_user(db, balance=100)
    # dual 模式按 source_text 长度扣款
    source = "你好世界测试"  # 6 chars
    with patch("app.services.review.review_service.dual_review", new=_fake_review_success):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/reviews", headers=headers, json={
                "mode": "dual",
                "source_text": source,
                "translated_text": "hello",
                "target_language": "en-GB",
            })
    assert resp.status_code == 200
    await db.refresh(user)
    assert user.credit_balance == 100 - 6
    consumes = (await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.tx_type == TxType.consume,
            CreditTransaction.user_id == user.id,
        )
    )).scalars().all()
    assert len(consumes) == 1


@pytest.mark.asyncio
async def test_failed_review_refunds(db: AsyncSession):
    user, headers = await _auth_user(db, balance=100)

    async def _boom(*a, **kw):
        raise RuntimeError("LLM down")

    with patch("app.services.review.review_service.dual_review", new=_boom):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/reviews", headers=headers, json={
                "mode": "dual",
                "source_text": "你好世界",
                "translated_text": "hello",
                "target_language": "en-GB",
            })
    # 服务端异常 → 500，但扣款发生在成功之后，所以未扣款
    assert resp.status_code == 500
    await db.refresh(user)
    assert user.credit_balance == 100  # unchanged


@pytest.mark.asyncio
async def test_low_balance_review_blocked_before_llm(db: AsyncSession):
    user, headers = await _auth_user(db, balance=3)

    async def _should_not_call(*a, **kw):
        raise AssertionError("review service should not be called")

    with patch("app.services.review.review_service.dual_review", new=_should_not_call):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/reviews", headers=headers, json={
                "mode": "dual",
                "source_text": "0123456789",
                "translated_text": "hello",
                "target_language": "en-GB",
            })

    assert resp.status_code == 402
    assert resp.json()["detail"] == "INSUFFICIENT_CREDITS"
    await db.refresh(user)
    assert user.credit_balance == 3


@pytest.mark.asyncio
async def test_review_idempotency_is_scoped_per_user(db: AsyncSession):
    user1, headers1 = await _auth_user(db, balance=100)
    user2, headers2 = await _auth_user(db, balance=100)
    source = "你好世界"
    payload = {
        "mode": "dual",
        "source_text": source,
        "translated_text": "hello",
        "target_language": "en-GB",
        "idempotency_key": "same-client-key",
    }

    with patch("app.services.review.review_service.dual_review", new=_fake_review_success):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.post("/api/reviews", headers=headers1, json=payload)
            resp2 = await client.post("/api/reviews", headers=headers2, json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    await db.refresh(user1)
    await db.refresh(user2)
    assert user1.credit_balance == 100 - len(source)
    assert user2.credit_balance == 100 - len(source)

    consumes = (await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.tx_type == TxType.consume,
            CreditTransaction.user_id.in_([user1.id, user2.id]),
        )
    )).scalars().all()
    assert len(consumes) == 2


@pytest.mark.asyncio
async def test_review_retry_with_same_key_deducts_once(db: AsyncSession):
    user, headers = await _auth_user(db, balance=100)
    source = "你好世界"
    payload = {
        "mode": "dual",
        "source_text": source,
        "translated_text": "hello",
        "target_language": "en-GB",
        "idempotency_key": "retry-key",
    }

    with patch("app.services.review.review_service.dual_review", new=_fake_review_success):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.post("/api/reviews", headers=headers, json=payload)
            resp2 = await client.post("/api/reviews", headers=headers, json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    await db.refresh(user)
    assert user.credit_balance == 100 - len(source)
