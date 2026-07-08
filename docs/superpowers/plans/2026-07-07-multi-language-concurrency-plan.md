# 多语言并发转译实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Celery 任务 `_run_translation` 的 `for lang` 串行循环改为 `asyncio.gather` 并发（`asyncio.Semaphore(MAX_CONCURRENT_LANGS=4)` 限流），把多语言总耗时从 `preprocess + N×(translate+risk)` 降到 `preprocess + ceil(N/4)×(translate+risk)`。

**Architecture:** 一个 Celery 任务内 `asyncio.gather` 各语言协程；每语言协程 `async with sem` + 独立 DB session（共享 engine/session_factory），跑现有每语言逻辑并 `return True/False`；preprocess 全局共享跑一次；`gather(return_exceptions=True)` 聚合 → `all(r is True)` 定 `job.status`。credits 已 `FOR UPDATE` 原子，不改。

**Tech Stack:** FastAPI, Celery, SQLAlchemy 2.0 (async), asyncio, pytest (DB 集成).

## Global Constraints

- credits 已并发安全（`SELECT ... FOR UPDATE`），**不改 credit 逻辑**。
- semaphore 在事件循环内创建（`asyncio.Semaphore(settings.MAX_CONCURRENT_LANGS)`），**不模块级**（避免跨 loop 绑定）。
- 每语言协程独立 DB session（共享 engine/session_factory），**不跨协程共享 session**。
- preprocess 全局共享跑一次（preamble）。
- `MAX_CONCURRENT_LANGS: int = 4`（config，可配）；engine `pool_size = MAX_CONCURRENT_LANGS + 2`、`max_overflow = 4`。
- 单语言失败 → `translated_text=None` + `status=failed` + 退款 + `return False`；其他继续；`all(r is True)` 聚合 `completed`/`partial`。
- 不改 streaming/`translate`/`risk`/`preprocess`/`make_chunk_writer` 逻辑、不改前端/WS/轮询、不改 `pipeline.translate` 签名。
- 后端测试 `pytest`；DB 集成测试需 pg（`docker-compose -f docker-compose.dev.yml up -d`）。
- main 分支开发，按任务频繁提交。

---

## File Structure

| 文件 | 动作 | 说明 |
|---|---|---|
| `backend/app/core/config.py` | 修改 | 新增 `MAX_CONCURRENT_LANGS: int = 4` |
| `backend/app/tasks.py` | 修改 | `_get_async_session` pool_size；`_run_translation` 重构为 preamble→gather→收尾；`select` 提到顶层 import |
| `backend/tests/test_tasks_concurrency.py` | 创建 | 并发上限 + 部分失败 DB 集成测试 |
| `backend/tests/test_credits_integration.py` | 修改 | `test_insufficient_balance_marks_partial` 改为 count-based 断言（并发下哪门语言失败不确定） |

---

### Task 1: 并发 `_run_translation`（config + pool_size + 重构 + 测试）

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/tasks.py`
- Test: `backend/tests/test_tasks_concurrency.py`（创建）
- Modify: `backend/tests/test_credits_integration.py`

**Interfaces:**
- Consumes: `pipeline.translate(..., on_chunk=)`（已支持）、`make_chunk_writer(tr, db)`（已有）、`credits_service.deduct_for_translation` / `refund_for_translation`（已原子）、`cultural_preprocess`。
- Produces: `_run_translation(job_id)` 内部并发执行各语言；`settings.MAX_CONCURRENT_LANGS` 控制并发上限。

**行为变更说明（重要）：** 并发下，余额不足以覆盖全部语言时，"哪门语言在扣分时 INSUFFICIENT" 不再确定（`FOR UPDATE` 串行扣分，先到先得）。结果仍正确（不超支、成功数 = floor(余额/单语言成本)、job=partial），但具体哪门失败不可预测。故 `test_insufficient_balance_marks_partial` 须改为 count-based 断言。

- [ ] **Step 1: 新增 config 字段**

修改 `backend/app/core/config.py`，在 `FRONTEND_URL` 之后新增一行：

```python
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_CONCURRENT_LANGS: int = 4
```

- [ ] **Step 2: 编写失败测试（并发上限）**

创建 `backend/tests/test_tasks_concurrency.py`：

```python
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
```

- [ ] **Step 3: 运行测试，确认失败**

确保 pg 已起：`docker compose -f docker-compose.dev.yml up -d`（从仓库根）。
Run: `cd backend && pytest tests/test_tasks_concurrency.py::test_languages_run_concurrently_bounded -v`
Expected: FAIL — 现有串行代码峰值并发=1，`assert active["peak"] >= 2` 失败。

- [ ] **Step 4: 实现 `_get_async_session` pool_size + 重构 `_run_translation`**

修改 `backend/app/tasks.py`。

**(a)** 顶层 import 区加 `from sqlalchemy import select`（在 `from sqlalchemy.ext.asyncio import AsyncSession` 之前）：

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
```

**(b)** `_get_async_session` 的 engine 绑定连接池（将 `engine = create_async_engine(settings.DATABASE_URL, echo=False)` 改为）：

```python
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=settings.MAX_CONCURRENT_LANGS + 2,
        max_overflow=4,
    )
```

**(c)** 用以下完整实现替换整个 `_run_translation` 函数（当前 `async def _run_translation(job_id: str):` 到 `await engine.dispose()` 整段，含其内联的 `from sqlalchemy import select`）：

```python
async def _run_translation(job_id: str):
    session_factory, engine = _get_async_session()
    # semaphore 必须在事件循环内创建（避免模块级跨 loop 绑定）
    sem = asyncio.Semaphore(settings.MAX_CONCURRENT_LANGS)
    try:
        # ---- preamble：取 job / 置 processing / preprocess（共享）----
        async with session_factory() as db:
            job = (await db.execute(
                select(TranslationJob).where(TranslationJob.id == uuid.UUID(job_id))
            )).scalar_one_or_none()
            if job is None:
                logger.error(f"Job {job_id} not found")
                return
            job.status = "processing"
            await db.commit()

            user_row = (await db.execute(select(User).where(User.id == job.user_id))).scalar_one()
            total_cost = len(job.source_text) * len(job.target_languages)
            cultural_constraints = None
            if job.cultural_sphere and user_row.credit_balance >= total_cost:
                cultural_constraints = await cultural_preprocess(
                    text=job.source_text,
                    cultural_sphere=job.cultural_sphere,
                    audience_type=job.audience_type or "general_public",
                    genre=job.genre,
                    llm_client=bailian_client,
                )
            # 捕获原语（job 对象 session 关闭后 detach）
            source_text = job.source_text
            target_languages = list(job.target_languages)
            user_id = job.user_id
            genre = job.genre
            strategy = job.strategy
            cultural_sphere = job.cultural_sphere
            audience_type = job.audience_type

        # ---- 每语言协程 ----
        async def run_one_lang(lang: str) -> bool:
            async with sem:
                async with session_factory() as db:
                    try:
                        tr = (await db.execute(
                            select(TranslationResult).where(
                                TranslationResult.job_id == uuid.UUID(job_id),
                                TranslationResult.language == lang,
                            )
                        )).scalar_one_or_none()
                        if tr is None:
                            tr = TranslationResult(job_id=uuid.UUID(job_id), language=lang, status="streaming")
                            db.add(tr)
                            await db.commit()
                            await db.refresh(tr)
                        else:
                            tr.status = "streaming"
                            await db.commit()

                        # 余额预检
                        user_row = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
                        cost = len(source_text)
                        if user_row.credit_balance < cost:
                            tr.status = "failed"
                            await db.commit()
                            return False

                        on_chunk = make_chunk_writer(tr, db)
                        output = await pipeline.translate(
                            source_text=source_text,
                            genre=genre,
                            strategy=strategy,
                            target_language=lang,
                            cultural_sphere=cultural_sphere,
                            audience_type=audience_type,
                            cultural_constraints=cultural_constraints,
                            db=db,
                            user_id=user_id,
                            on_chunk=on_chunk,
                        )
                        tr.translated_text = output["translated_text"]
                        tr.risk_annotations = output["risk_annotations"]
                        tr.cultural_adaptation = output["cultural_adaptation"]
                        tr.acceptance_score = output["acceptance_score"]
                        tr.status = "completed"

                        # 决策日志 — 尽力而为，失败不阻断
                        decision_entries = output.get("decision_entries") or []
                        if decision_entries:
                            try:
                                log_ids = await save_decision_logs(
                                    db, job_id=uuid.UUID(job_id), result_id=tr.id, entries=decision_entries,
                                )
                                tr.decision_log_ids = log_ids
                            except Exception as e:
                                logger.warning(f"Decision log save failed for job {job_id} lang {lang}: {e}")

                        # 扣分（FOR UPDATE 原子）
                        deduct_res, _ = await credits_service.deduct_for_translation(
                            db, user_id, source_text, lang, uuid.UUID(job_id),
                        )
                        if deduct_res is DeductResult.INSUFFICIENT:
                            tr.status = "failed"
                            tr.translated_text = None
                            await db.commit()
                            return False

                        await db.commit()
                        return True

                    except Exception as e:
                        logger.error(f"Translation failed for job {job_id} lang {lang}: {e}")
                        tr = (await db.execute(
                            select(TranslationResult).where(
                                TranslationResult.job_id == uuid.UUID(job_id),
                                TranslationResult.language == lang,
                            )
                        )).scalar_one_or_none()
                        if tr:
                            tr.translated_text = None
                            tr.status = "failed"
                            await db.commit()
                            try:
                                await credits_service.refund_for_translation(
                                    db, user_id, source_text, lang, uuid.UUID(job_id),
                                )
                            except Exception as refund_err:
                                logger.warning(f"Refund failed for job {job_id} lang {lang}: {refund_err}")
                        return False

        # ---- gather 并发 ----
        results = await asyncio.gather(
            *(run_one_lang(lang) for lang in target_languages),
            return_exceptions=True,
        )
        all_success = all(r is True for r in results)

        # ---- 收尾：聚合 job.status ----
        async with session_factory() as db:
            job = (await db.execute(
                select(TranslationJob).where(TranslationJob.id == uuid.UUID(job_id))
            )).scalar_one_or_none()
            if job:
                job.status = "completed" if all_success else "partial"
                await db.commit()
    finally:
        await engine.dispose()
```

- [ ] **Step 5: 运行新测试，确认通过**

Run: `cd backend && pytest tests/test_tasks_concurrency.py -v`
Expected: PASS（2 个用例；峰值并发=2）。

- [ ] **Step 6: 更新 `test_insufficient_balance_marks_partial` 为 count-based 断言**

修改 `backend/tests/test_credits_integration.py` 的 `test_insufficient_balance_marks_partial`。并发下哪门语言 INSUFFICIENT 不确定，改为断言「恰好一成功一失败」。将该测试的尾部：

```python
    results = (await db.execute(
        select(TranslationResult).where(TranslationResult.job_id == job.id)
    )).scalars().all()
    by_lang = {r.language: r for r in results}
    assert by_lang["en-GB"].status == "completed"
    assert by_lang["ja-JP"].status == "failed"

    await db.refresh(job)
    assert job.status == "partial"
```

改为：

```python
    # 并发下哪门语言 INSUFFICIENT 不确定（FOR UPDATE 先到先得），仅断言计数
    results = (await db.execute(
        select(TranslationResult).where(TranslationResult.job_id == job.id)
    )).scalars().all()
    statuses = sorted(r.status for r in results)
    assert statuses == ["completed", "failed"]  # 恰好一成功一失败

    await db.refresh(job)
    assert job.status == "partial"
```

（`assert user.credit_balance == 1` 保持不变——仅 1 门扣 2，余额 3→1 是确定的。）

- [ ] **Step 7: 回归既有集成测试**

Run: `cd backend && pytest tests/test_credits_integration.py tests/test_tasks_streaming.py tests/test_translation_streaming.py tests/test_decision_extraction.py -v`
Expected: 全部 PASS（`test_insufficient_balance_marks_partial` 更新后通过；其余行为不变）。

- [ ] **Step 8: 提交**

```bash
git add backend/app/core/config.py backend/app/tasks.py backend/tests/test_tasks_concurrency.py backend/tests/test_credits_integration.py
git commit -m "feat(backend): run target languages concurrently with bounded semaphore"
```

---

### Task 2: 全量校验

**Files:** 无（仅运行校验）

- [ ] **Step 1: 确认 pg 运行**

Run: `docker compose -f docker-compose.dev.yml ps`（从仓库根）
Expected: pg + redis 处于 running（DB 集成测试需要）。若未起：`docker compose -f docker-compose.dev.yml up -d`。

- [ ] **Step 2: 后端全量测试**

Run: `cd backend && pytest -v`
Expected: 全部 PASS（含新并发测试 + 既有集成测试 + 单元测试）。允许与本次无关的既有失败，但需确认非本改动引入。

- [ ] **Step 3: 核对改动范围**

Run: `git diff <BASE>..HEAD --stat`（BASE 为本计划开始 commit）
Expected: 仅包含 `config.py`、`tasks.py`、`test_tasks_concurrency.py`（新）、`test_credits_integration.py` 的合理变更；无对 `translation.py`、`credits.py`、`bailian.py`、前端、WS 的改动。

---

## Self-Review

**1. Spec 覆盖：**
- `MAX_CONCURRENT_LANGS: int = 4` config → Task 1 Step 1。
- engine `pool_size = MAX_CONCURRENT_LANGS+2` → Task 1 Step 4(b)。
- `_run_translation` preamble→gather→收尾 + semaphore 循环内创建 + 每协程独立 session + `return True/False` + `all(r is True)` 聚合 → Task 1 Step 4(c)。
- 单语言失败 → failed+退款+return False → Task 1 Step 4(c) except 块。
- preprocess 共享一次 → Task 1 Step 4(c) preamble。
- credits 不改（FOR UPDATE）→ 未触及 `credits.py`，Task 2 Step 3 核对。
- 并发上限测试 + 部分失败测试 → Task 1 Step 2。
- 前端无改动 → Task 2 Step 3 核对。
- 非目标（fan-out、改 streaming/translate/risk、改前端）→ 未触及。

**2. 占位符扫描：** 无 TBD/TODO；每个代码步骤含完整代码；无"类似 Task N"。

**3. 类型一致性：** `run_one_lang(lang: str) -> bool` 定义与 `gather` 调用一致；`make_chunk_writer(tr, db)` 沿用 Task 既有签名；`MAX_CONCURRENT_LANGS` 在 config、semaphore、pool_size、测试 patch 四处一致；`uuid.UUID(job_id)` 转换在所有 `TranslationResult`/`save_decision_logs`/`deduct_for_translation`/`refund_for_translation` 调用一致。

**4. 行为变更已处理：** `test_insufficient_balance_marks_partial` 改 count-based（Task 1 Step 6），应对并发下「哪门语言 INSUFFICIENT 不确定」——结果仍正确（不超支、一成功一失败、partial、余额=1 确定）。
