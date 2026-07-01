"""Test decision_log service: save and query decision logs."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision_log import DecisionLog
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User
from app.services.decision_log import (
    get_decision_logs_by_job,
    get_decision_logs_by_result,
    save_decision_logs,
)


async def _setup_job_and_result(db: AsyncSession):
    """Create a user, job, and result for testing."""
    user = User(
        id=uuid.uuid4(),
        username=f"declog_user_{uuid.uuid4().hex[:8]}",
        hashed_password="fakehash",
    )
    db.add(user)
    await db.commit()

    job = TranslationJob(
        user_id=user.id,
        source_text="测试原文",
        genre="political",
        strategy="semantic_equivalence",
        target_languages=["en-GB"],
        status="completed",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    result = TranslationResult(
        job_id=job.id, language="en-GB", status="completed", translated_text="test"
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return job, result


@pytest.mark.asyncio
async def test_save_decision_logs_returns_ids(db: AsyncSession):
    """save_decision_logs should create rows and return their IDs."""
    job, result = await _setup_job_and_result(db)
    entries = [
        {
            "stage": "preprocess",
            "decision_type": "culture_term_adaptation",
            "source_phrase": "一带一路",
            "target_phrase": "BRI",
            "decision": "采用 analogical 策略翻译「一带一路」",
            "reasoning": "目标文化有相近概念",
            "confidence": "high",
            "metadata": {"adaptation_strategy": "analogical"},
        },
        {
            "stage": "risk",
            "decision_type": "risk_identified",
            "source_phrase": None,
            "target_phrase": "some phrase",
            "decision": "标记为 high 风险：cognitive_bias",
            "reasoning": "可能引起误解",
            "confidence": "high",
            "metadata": {"risk_level": "high", "risk_type": "cognitive_bias"},
        },
    ]
    ids = await save_decision_logs(db, job.id, result.id, entries)
    assert len(ids) == 2
    assert all(isinstance(i, uuid.UUID) for i in ids)


@pytest.mark.asyncio
async def test_get_decision_logs_by_result(db: AsyncSession):
    """get_decision_logs_by_result should return logs for the given result."""
    job, result = await _setup_job_and_result(db)
    entries = [
        {"stage": "preprocess", "decision_type": "culture_term_adaptation",
         "source_phrase": "A", "target_phrase": "B", "decision": "d1",
         "reasoning": "r1", "confidence": "high", "metadata": {}},
        {"stage": "risk", "decision_type": "risk_identified",
         "source_phrase": None, "target_phrase": "C", "decision": "d2",
         "reasoning": "r2", "confidence": "medium", "metadata": {}},
    ]
    await save_decision_logs(db, job.id, result.id, entries)
    logs = await get_decision_logs_by_result(db, result.id)
    assert len(logs) == 2
    # Ordered by stage then created_at: preprocess before risk
    assert logs[0].stage == "preprocess"
    assert logs[1].stage == "risk"


@pytest.mark.asyncio
async def test_get_decision_logs_by_job(db: AsyncSession):
    """get_decision_logs_by_job should return all logs for the job."""
    job, result = await _setup_job_and_result(db)
    entries = [
        {"stage": "preprocess", "decision_type": "culture_term_adaptation",
         "source_phrase": "A", "target_phrase": "B", "decision": "d1",
         "reasoning": "r1", "confidence": "high", "metadata": {}},
    ]
    await save_decision_logs(db, job.id, result.id, entries)
    logs = await get_decision_logs_by_job(db, job.id)
    assert len(logs) == 1
    assert logs[0].stage == "preprocess"


@pytest.mark.asyncio
async def test_save_empty_entries_returns_empty(db: AsyncSession):
    """save_decision_logs with empty list should return empty list."""
    job, result = await _setup_job_and_result(db)
    ids = await save_decision_logs(db, job.id, result.id, [])
    assert ids == []


def test_stage_order_includes_cultural_detect():
    """_STAGE_ORDER 应包含 cultural_detect 阶段，且与 preprocess 同序、先于 glossary。

    纯单元测试，不依赖 DB。验证输入期文化识别阶段的排序优先级正确。
    """
    from app.services.decision_log import _STAGE_ORDER

    assert "cultural_detect" in _STAGE_ORDER
    assert _STAGE_ORDER["cultural_detect"] == _STAGE_ORDER["preprocess"]
    assert _STAGE_ORDER["cultural_detect"] < _STAGE_ORDER["glossary"]

    # 模拟一组跨阶段日志，按 _STAGE_ORDER 排序应得正确顺序
    fake_logs = [
        type("L", (), {"stage": "glossary", "created_at": 1})(),
        type("L", (), {"stage": "cultural_detect", "created_at": 2})(),
        type("L", (), {"stage": "preprocess", "created_at": 3})(),
        type("L", (), {"stage": "risk", "created_at": 4})(),
    ]
    ordered = sorted(fake_logs, key=lambda r: (_STAGE_ORDER.get(r.stage, 99), r.created_at))
    stages = [r.stage for r in ordered]
    # preprocess 与 cultural_detect 同序(0)，按 created_at 升序；glossary=1；risk=3
    assert stages == ["cultural_detect", "preprocess", "glossary", "risk"]


@pytest.mark.asyncio
async def test_acceptance_stage_ordered_after_suggestion(db):
    from app.services.decision_log import _STAGE_ORDER
    assert "acceptance" in _STAGE_ORDER
    assert _STAGE_ORDER["acceptance"] > _STAGE_ORDER["suggestion"]
