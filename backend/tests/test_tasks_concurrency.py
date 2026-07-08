"""多语言并发转译集成测试：验证 asyncio.gather + Semaphore 限流与部分失败聚合。

需 pg：docker-compose -f docker-compose.dev.yml up -d
"""
import asyncio
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.job import TranslationResult
from app.models.user import User
from app.models.job import TranslationJob
from app.tasks import _run_translation


async def _seed_job(db, source_text, langs, balance=10000):
    user = User(
        id=uuid.uuid4(),
        username=f"conc_{uuid.uuid4().hex[:8]}",
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


_SUCCESS_OUTPUT = {
    "translated_text": "translated",
    "risk_annotations": [],
    "cultural_adaptation": None,
    "acceptance_score": -1,
    "decision_entries": [],
}


@pytest.mark.asyncio
async def test_languages_run_concurrently_bounded(db: AsyncSession):
    """4 语言、MAX_CONCURRENT_LANGS=2：峰值并发 ≥2（确并发）且 ≤2（受限），全部 completed。"""
    user, job = await _seed_job(db, "你好世界", ["en-GB", "ja-JP", "fr-FR", "de-DE"], balance=10000)
    active = {"n": 0, "peak": 0}

    async def _counting_translate(*a, **kw):
        active["n"] += 1
        active["peak"] = max(active["peak"], active["n"])
        await asyncio.sleep(0.1)
        active["n"] -= 1
        return dict(_SUCCESS_OUTPUT)

    with patch("app.tasks.cultural_preprocess", return_value=None), \
         patch("app.tasks.pipeline.translate", new=_counting_translate), \
         patch.object(settings, "MAX_CONCURRENT_LANGS", 2):
        await _run_translation(str(job.id))

    assert active["peak"] >= 2  # 串行代码峰值=1，会失败 → RED
    assert active["peak"] <= 2  # 受 semaphore 限流

    results = (await db.execute(
        select(TranslationResult).where(TranslationResult.job_id == job.id)
    )).scalars().all()
    assert all(r.status == "completed" for r in results)
    await db.refresh(job)
    assert job.status == "completed"


@pytest.mark.asyncio
async def test_partial_failure_under_concurrency(db: AsyncSession):
    """4 语言、MAX=2、其一抛错：失败语言 failed，其余 completed，job=partial，仅扣成功的。"""
    user, job = await _seed_job(db, "你好", ["en-GB", "ja-JP", "fr-FR", "de-DE"], balance=10000)

    async def _translate(*a, **kw):
        if kw.get("target_language") == "ja-JP":
            raise RuntimeError("ja failed")
        return dict(_SUCCESS_OUTPUT)

    with patch("app.tasks.cultural_preprocess", return_value=None), \
         patch("app.tasks.pipeline.translate", new=_translate), \
         patch.object(settings, "MAX_CONCURRENT_LANGS", 2):
        await _run_translation(str(job.id))

    await db.refresh(user)
    assert user.credit_balance == 10000 - 2 * 3  # 仅 3 个成功语言各扣 2

    results = (await db.execute(
        select(TranslationResult).where(TranslationResult.job_id == job.id)
    )).scalars().all()
    by_lang = {r.language: r for r in results}
    assert by_lang["ja-JP"].status == "failed"
    for lang in ["en-GB", "fr-FR", "de-DE"]:
        assert by_lang[lang].status == "completed"

    await db.refresh(job)
    assert job.status == "partial"
