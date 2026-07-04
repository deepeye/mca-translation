"""CreditsService 核心逻辑测试：扣款 / 退还 / 幂等 / 不足 / 管理员调整 / 趋势。"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditTransaction, TxType
from app.models.user import User
from app.services.credits import CreditsService, DeductResult

credits = CreditsService()


async def _make_user(db, balance=1000, admin=False):
    user = User(
        id=uuid.uuid4(),
        username=f"svc_user_{uuid.uuid4().hex[:8]}",
        hashed_password="fakehash",
        credit_balance=balance,
        is_admin=admin,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_deduct_for_translation_decrements_balance(db: AsyncSession):
    user = await _make_user(db, balance=100)
    job_id = uuid.uuid4()
    result, balance = await credits.deduct_for_translation(db, user.id, "你好世界", "en-GB", job_id)
    assert result is DeductResult.OK
    assert balance == 96  # 4 chars
    rows = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == user.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].delta == -4
    assert rows[0].tx_type == TxType.consume


@pytest.mark.asyncio
async def test_deduct_insufficient_returns_no_row(db: AsyncSession):
    user = await _make_user(db, balance=2)
    result, balance = await credits.deduct_for_translation(db, user.id, "一二三四五", "en-GB", uuid.uuid4())
    assert result is DeductResult.INSUFFICIENT
    assert balance == 2  # unchanged
    rows = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == user.id))).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_refund_is_idempotent(db: AsyncSession):
    user = await _make_user(db, balance=100)
    job_id = uuid.uuid4()
    await credits.deduct_for_translation(db, user.id, "你好", "en-GB", job_id)  # -2 → 98
    r1, b1 = await credits.refund_for_translation(db, user.id, "你好", "en-GB", job_id)  # +2 → 100
    r2, b2 = await credits.refund_for_translation(db, user.id, "你好", "en-GB", job_id)  # no-op
    assert r1 is DeductResult.OK and b1 == 100
    assert r2 is DeductResult.ALREADY_APPLIED and b2 == 100
    rows = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == user.id))).scalars().all()
    assert len(rows) == 2  # one consume, one refund — no duplicate refund


@pytest.mark.asyncio
async def test_refund_without_prior_consume_is_noop(db: AsyncSession):
    user = await _make_user(db, balance=100)
    result, balance = await credits.refund_for_translation(db, user.id, "你好", "en-GB", uuid.uuid4())
    assert result is DeductResult.ALREADY_APPLIED  # nothing to refund
    assert balance == 100
    rows = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == user.id))).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_deduct_for_review_uses_text_length(db: AsyncSession):
    user = await _make_user(db, balance=50)
    review_id = uuid.uuid4()
    result, balance = await credits.deduct_for_review(db, user.id, 10, review_id, "dual")
    assert result is DeductResult.OK
    assert balance == 40


@pytest.mark.asyncio
async def test_admin_topup_increments(db: AsyncSession):
    user = await _make_user(db, balance=100)
    admin = await _make_user(db, balance=0, admin=True)
    new_balance = await credits.admin_adjust(db, user.id, 500, admin.id, "月度充值")
    assert new_balance == 600
    rows = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == user.id))).scalars().all()
    assert rows[0].delta == 500
    assert rows[0].tx_type == TxType.admin_topup


@pytest.mark.asyncio
async def test_admin_revoke_clamps_at_zero(db: AsyncSession):
    user = await _make_user(db, balance=100)
    admin = await _make_user(db, balance=0, admin=True)
    new_balance = await credits.admin_adjust(db, user.id, -150, admin.id, "回收")
    assert new_balance == 0  # clamped, not -50
    rows = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == user.id))).scalars().all()
    assert rows[0].delta == -100  # actual applied delta
    assert rows[0].tx_type == TxType.admin_revoke


@pytest.mark.asyncio
async def test_get_trend_groups_by_day(db: AsyncSession):
    user = await _make_user(db, balance=10000)
    # 三笔扣款，分布在今天
    await credits.deduct_for_translation(db, user.id, "一二", "en-GB", uuid.uuid4())   # -2
    await credits.deduct_for_translation(db, user.id, "三四五", "en-GB", uuid.uuid4())  # -3
    trend = await credits.get_trend(db, user.id, days=7)
    assert isinstance(trend, list)
    # 最近一天的总消耗应为 5
    today_entry = trend[-1]
    assert today_entry["consumed"] == 5
    assert "date" in today_entry


@pytest.mark.asyncio
async def test_get_transactions_newest_first(db: AsyncSession):
    user = await _make_user(db, balance=1000)
    for _ in range(3):
        await credits.deduct_for_translation(db, user.id, "字", "en-GB", uuid.uuid4())
    txs = await credits.get_transactions(db, user.id, limit=10)
    assert len(txs) == 3
    assert txs[0].created_at >= txs[1].created_at
