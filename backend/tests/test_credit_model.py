"""CreditTransaction model 与 User 信用分字段的单元测试。"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditTransaction, TxType
from app.models.user import User


@pytest.mark.asyncio
async def test_user_defaults_credit_balance_and_admin(db: AsyncSession):
    """新建用户默认 credit_balance=1000，is_admin=False，is_active=True，deleted_at=NULL。"""
    user = User(
        id=uuid.uuid4(),
        username=f"credit_user_{uuid.uuid4().hex[:8]}",
        hashed_password="fakehash",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    assert user.credit_balance == 1000
    assert user.is_admin is False
    assert user.is_active is True
    assert user.deleted_at is None


@pytest.mark.asyncio
async def test_credit_transaction_persists_all_fields(db: AsyncSession):
    """CreditTransaction 各字段可正确持久化与读取。"""
    user = User(
        id=uuid.uuid4(),
        username=f"tx_user_{uuid.uuid4().hex[:8]}",
        hashed_password="fakehash",
    )
    db.add(user)
    await db.commit()

    job_id = uuid.uuid4()
    tx = CreditTransaction(
        id=uuid.uuid4(),
        user_id=user.id,
        delta=-42,
        tx_type=TxType.consume,
        reason="翻译消耗: en-GB",
        job_id=job_id,
        idempotency_key=f"consume:{job_id}:en-GB",
    )
    db.add(tx)
    await db.commit()

    result = await db.execute(select(CreditTransaction).where(CreditTransaction.id == tx.id))
    loaded = result.scalar_one()
    assert loaded.delta == -42
    assert loaded.tx_type == TxType.consume
    assert loaded.reason == "翻译消耗: en-GB"
    assert loaded.job_id == job_id
    assert loaded.review_id is None
    assert loaded.idempotency_key == f"consume:{job_id}:en-GB"


@pytest.mark.asyncio
async def test_idempotency_key_is_unique(db: AsyncSession):
    """相同 idempotency_key 二次插入应抛唯一约束错误。"""
    user = User(
        id=uuid.uuid4(),
        username=f"dup_user_{uuid.uuid4().hex[:8]}",
        hashed_password="fakehash",
    )
    db.add(user)
    await db.commit()

    key = "consume:job-1:en-GB"
    for delta in (-10, -10):
        db.add(CreditTransaction(
            id=uuid.uuid4(), user_id=user.id, delta=delta,
            tx_type=TxType.consume, reason="t", idempotency_key=key,
        ))
    with pytest.raises(Exception):
        await db.commit()
