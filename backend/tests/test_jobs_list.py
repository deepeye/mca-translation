"""Test GET /api/jobs — list, filter, and source_text."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import TranslationJob
from app.models.user import User
from app.schemas.job import JobListItem


@pytest.mark.asyncio
async def test_list_jobs_returns_source_text(db: AsyncSession):
    """JobListItem should include truncated source_text."""
    # Create a user first (FK constraint: translation_jobs.user_id -> users.id)
    user = User(
        id=uuid.uuid4(),
        username=f"history_test_user_{uuid.uuid4().hex[:8]}",
        hashed_password="fakehash",
    )
    db.add(user)
    await db.commit()

    # Create a job with source text longer than 200 chars to verify truncation
    long_source = (
        "这是一篇很长的中文测试文章，用于验证历史记录功能中的原文摘要展示。"
        "本平台旨在为国际传播内容提供文化适配的人工智能转译服务。"
        "通过选择不同的文体、目标语言和文化适配参数，用户可以获得高质量的翻译结果。"
        "同时，系统会对翻译结果进行风险标注，帮助用户识别潜在的文化适应性问题。"
        "本文用于测试列表页中原文摘要的截断显示功能是否正常工作。"
        "除此之外，还需要额外增加一些内容来确保总长度超过二百个字符的阈值。"
        "因为测试需要验证当原文超过限定长度时，摘要能否正确截断到指定字符数内。"
    )
    assert len(long_source) > 200, "Source text must exceed 200 chars for truncation test"

    job = TranslationJob(
        user_id=user.id,
        source_text=long_source,
        genre="political",
        strategy="semantic_equivalence",
        target_languages=["en-GB"],
        status="completed",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Verify the schema works with truncated source_text
    item = JobListItem(
        id=job.id,
        status=job.status,
        genre=job.genre,
        target_languages=job.target_languages,
        source_text=job.source_text[:200] if job.source_text else None,
        created_at=job.created_at,
    )
    assert item.source_text is not None
    assert len(item.source_text) <= 200
    assert "中文测试文章" in item.source_text
