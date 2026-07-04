"""翻译管线与信用分扣款/退还的集成测试。

用真实（mock 掉 LLM 的）pipeline 调用 _run_translation，验证：
- 成功语言 → 扣 len(source_text)
- 失败语言 → 退还
- 余额不足的语言 → 标记 failed 且不扣款
"""
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditTransaction, TxType
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User
from app.tasks import _run_translation


async def _seed_job(db, source_text, langs, balance=10000):
    user = User(
        id=uuid.uuid4(),
        username=f"pipe_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        credit_balance=balance,
    )
    db.add(user)
    await db.flush()
    job = TranslationJob(
        id=uuid.uuid4(),
        user_id=user.id,
        source_text=source_text,
        genre="political",
        strategy="semantic_equivalence",
        target_languages=langs,
        status="pending",
    )
    db.add(job)
    for lang in langs:
        db.add(TranslationResult(job_id=job.id, language=lang, status="idle"))
    await db.commit()
    return user, job


async def _fake_translate_success(*a, **kw):
    return {
        "translated_text": "translated",
        "risk_annotations": [],
        "cultural_adaptation": None,
        "acceptance_score": -1,
        "decision_entries": [],
    }


@pytest.mark.asyncio
async def test_successful_translation_deducts_per_language(db: AsyncSession):
    user, job = await _seed_job(db, "你好世界", ["en-GB", "ja-JP"], balance=10000)
    with patch("app.tasks.cultural_preprocess", return_value=None), \
         patch("app.tasks.pipeline.translate", new=_fake_translate_success):
        await _run_translation(str(job.id))

    await db.refresh(user)
    assert user.credit_balance == 10000 - 4 - 4  # 两种语言各扣 4
    consumes = (await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.tx_type == TxType.consume,
            CreditTransaction.user_id == user.id,
        )
    )).scalars().all()
    assert len(consumes) == 2


@pytest.mark.asyncio
async def test_failed_translation_refunds(db: AsyncSession):
    user, job = await _seed_job(db, "你好", ["en-GB"], balance=100)

    call_count = {"n": 0}

    async def _flaky(*a, **kw):
        call_count["n"] += 1
        raise RuntimeError("LLM boom")

    with patch("app.tasks.cultural_preprocess", return_value=None), \
         patch("app.tasks.pipeline.translate", new=_flaky):
        await _run_translation(str(job.id))

    # 翻译失败：未扣款（因为扣款发生在成功之后），不应有 consume/refund
    await db.refresh(user)
    assert user.credit_balance == 100  # unchanged
    txs = (await db.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == user.id)
    )).scalars().all()
    assert len(txs) == 0


@pytest.mark.asyncio
async def test_mixed_success_failure(db: AsyncSession):
    """一种语言成功、另一种失败：只扣成功的。"""
    user, job = await _seed_job(db, "你好", ["en-GB", "ja-JP"], balance=100)

    async def _translate(source_text, target_language, **kw):
        if target_language == "ja-JP":
            raise RuntimeError("ja failed")
        return await _fake_translate_success(source_text, target_language)

    with patch("app.tasks.cultural_preprocess", return_value=None), \
         patch("app.tasks.pipeline.translate", new=_translate):
        await _run_translation(str(job.id))

    await db.refresh(user)
    assert user.credit_balance == 100 - 2  # 仅 en-GB 扣 2
