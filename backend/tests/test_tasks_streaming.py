"""Celery 流式落库节流单元测试。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.tasks import make_chunk_writer


@pytest.mark.asyncio
async def test_make_chunk_writer_throttles_within_interval():
    tr = SimpleNamespace(translated_text=None)
    commits = []
    db = SimpleNamespace(commit=AsyncMock(side_effect=lambda: commits.append(1)))

    writer = make_chunk_writer(tr, db, interval=1.0)

    # 模拟时间推进：100.0 首次写、100.5 节流跳过、101.5 再次写
    with patch("app.tasks.time.monotonic", side_effect=[100.0, 100.5, 101.5]):
        await writer("a")
        await writer("ab")
        await writer("abc")

    assert len(commits) == 2  # 首次 + 第三次；第二次被节流
    assert tr.translated_text == "abc"


@pytest.mark.asyncio
async def test_make_chunk_writer_writes_first_chunk_immediately():
    tr = SimpleNamespace(translated_text=None)
    db = SimpleNamespace(commit=AsyncMock())

    writer = make_chunk_writer(tr, db, interval=1.0)

    with patch("app.tasks.time.monotonic", side_effect=[1000.0]):
        await writer("first")

    db.commit.assert_awaited_once()
    assert tr.translated_text == "first"
