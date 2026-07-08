# 多语言并发转译设计

## 背景

点击「开始转译」后，Celery 任务 `_run_translation`（`backend/app/tasks.py`）以 `for lang in job.target_languages:` **串行**跑各目标语言，每语言执行 `glossary → translate(qwen-max 流式) → risk(qwen-plus)`。总壁钟时间 ≈ `preprocess + N × (translate + risk)`，N 为语言数。诊断结论：`translate × N` 是主瓶颈，串行使其线性放大。

流式输出（已实现）只改善感知延迟，不降总耗时。本设计通过**多语言并发**把总耗时降到 `preprocess + ceil(N / MAX_CONCURRENT_LANGS) × (translate + risk)`。

关键现成条件：
- **credits 已并发安全**：`credits_service._apply` 用 `SELECT ... FOR UPDATE` 锁用户行后校验+更新余额（`app/services/credits.py`），`deduct_for_translation` 原子，并发扣分不会超支——无需改 credit 逻辑。
- **semaphore 先例**：`app/services/acceptance_scorer.py` 已用 `asyncio.Semaphore(5)` 限流 LLM 并发。
- 每语言 `TranslationResult` 行在 `create_job` 时已建好，无创建竞争。
- 流式 `on_chunk`（`make_chunk_writer`）已就绪，每语言可独立节流落库。

## 目标

- 各目标语言在单个 Celery 任务内并发执行（`asyncio.gather`），受 `asyncio.Semaphore(MAX_CONCURRENT_LANGS=4)` 限流。
- 每语言协程使用独立 DB session，避免 async session 跨协程共享。
- preprocess 全局共享跑一次（不变）。
- 单语言失败不影响其他语言；作业状态正确聚合为 `completed` / `partial`。
- credits 不超支（复用现有 `FOR UPDATE` 原子扣分）。
- `MAX_CONCURRENT_LANGS` 可经 settings 配置；engine 连接池跟随。

## 非目标

- 不改 credit 逻辑（已原子）。
- 不做 per-language Celery fan-out / chord（方案 B，复杂度不划算）。
- 不改 streaming / `translate` / `risk` / `preprocess` / `make_chunk_writer` 逻辑。
- 不改前端、WS、轮询。
- 不改 `pipeline.translate` 签名。

## 方案选型

选用 **A. 现有 Celery 任务内 `asyncio.gather` + 有界 semaphore**：

- 一个 Celery 任务 `run_translation` → `asyncio.run(_run_translation)`。
- `_run_translation`：preamble（preprocess 共享）→ 为每语言构造协程 → `asyncio.gather(*coros, return_exceptions=True)`，用 `asyncio.Semaphore(MAX_CONCURRENT_LANGS)` 限流。
- 每语言协程开自己的 DB session（共享 engine/session_factory），跑现有每语言逻辑，`return True/False` 表示成功/失败。
- 主协程聚合结果定 `job.status`。

相比 B（每语言一个 Celery 子任务 + chord 聚合），A 无需 chord 协调、无多任务写 `job.status` 竞争、preprocess 天然共享、状态聚合简单。semaphore 限流防 DashScope qwen-max 并发上限（429）与 DB 连接池打满。

## 架构与组件变更

### 1. `backend/app/core/config.py`

新增设置：

```python
MAX_CONCURRENT_LANGS: int = 4
```

### 2. `backend/app/tasks.py` `_run_translation` 重构（核心改动）

**(a) `_get_async_session` 的 engine 绑定连接池大小：**

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=settings.MAX_CONCURRENT_LANGS + 2,
    max_overflow=4,
)
```

`pool_size` 跟随 `MAX_CONCURRENT_LANGS`，避免协程排队等连接（preamble/收尾 session 与 gather 协程基本不重叠，+2 为安全余量）。

**(b) `_run_translation` 改为 preamble → gather → 收尾 三段：**

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
                        # 取/建 tr
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

                        # 流式翻译 + 落库节流
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

                        # 决策日志（尽力而为）
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
                        # re-fetch tr（可能 mid-mutation）→ failed + 退款
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

`run_one_lang` 为嵌套闭包（捕获 `sem` / `session_factory` / 原语），逻辑与现有每语言块一致，仅多了 `async with sem` + 独立 session + `return bool`。`make_chunk_writer(tr, db)` 用本协程的 `tr`/`db`，`on_chunk` 闭包写本协程 session，无跨协程共享。

### 3. 其它

- `backend/app/services/translation.py`：无改动。
- `backend/app/services/credits.py`：无改动（已原子）。
- 前端、WS、轮询：无改动。

## 数据流

1. 点击 → `POST /api/jobs` → Celery `run_translation`。
2. preamble：`job.status=processing` → preprocess（1×，qwen-plus，共享）→ 捕获原语。
3. `gather` 最多 4 路并发：每路 `sem` 获取 → 独立 session → `tr.status=streaming` → 余额预检 → `translate(on_chunk=make_chunk_writer)` 流式（`on_chunk` 每 1s 落库部分译文）→ risk → 决策日志 → 原子扣分 → `return True`；失败 `return False`。
4. 前端 2s 轮询看到多语言译文同时增长（各自 `▍` 光标）。
5. 收尾：`all_success = all(r is True)` → re-fetch job → `completed` / `partial`。

## 错误处理

- 单语言失败：协程 `except` → re-fetch `tr` → `translated_text=None` + `status=failed` + 退款 → `return False`；其他协程不受影响；`all_success=False` → `job.status=partial`。
- `gather(return_exceptions=True)`：协程内 try/except 已兜底；逃逸异常也被捕获，`r is True` 为 False，计入失败。
- 余额不足某语言：`status=failed`，`return False`（现状语义）；不影响其他语言（总余额已 preamble 预检）。
- `MAX_CONCURRENT_LANGS` ≥ 语言数：semaphore 不阻塞，全部并发。
- 单语言作业：gather 1 路，行为同现状。
- engine `pool_size = MAX_CONCURRENT_LANGS+2`，避免协程等连接。
- DashScope 429：semaphore 限并发 ≤4，降低触发概率；若仍 429，按现有 LLM 调用失败语义处理（该语言 failed）。

## 测试计划（后端 pytest）

- **DB 集成测试**（沿用 `tests/test_credits_integration.py` 的 `db` fixture 模式，需 pg：`docker-compose -f docker-compose.dev.yml up -d`）：
  - **并发上限**：种子 job（多语言）+ user（充足余额）+ 各语言 result 行；mock `pipeline.translate` 为「`await asyncio.sleep(短延时)` + 记录当前并发计数（进入 +1 / 退出 -1，断言峰值 ≤ `MAX_CONCURRENT_LANGS`）」，mock `cultural_preprocess` 跳过；跑 `_run_translation`；断言峰值并发 ≤ 4、各语言 `completed`、`job.status=completed`。
  - **部分失败**：mock 某语言 `pipeline.translate` 抛错 → 该语言 `status=failed` + 退款、其他 `completed`、`job.status=partial`。
- **现有 `tests/test_tasks_streaming.py`**：`make_chunk_writer` 节流测试不变，仍通过。
- **现有 `tests/test_translation_streaming.py` / `test_decision_extraction.py` 等**：不受影响（`pipeline.translate` 签名未变），回归通过。

## 验收标准

- [ ] 多语言作业各语言并发执行（受 semaphore 限 ≤ `MAX_CONCURRENT_LANGS`），总耗时显著低于串行。
- [ ] 最大并发数 ≤ `MAX_CONCURRENT_LANGS`（DB 集成测试可证）。
- [ ] 单语言失败 → 该语言 `failed` + 退款，作业 `partial`，其他语言不受影响。
- [ ] 流式逐步出字仍正常（每语言各自 `on_chunk`）。
- [ ] credits 不超支（复用 `FOR UPDATE` 原子扣分，无新增竞争）。
- [ ] `MAX_CONCURRENT_LANGS` 可经 settings 配置；engine `pool_size` 跟随。
- [ ] 后端测试通过（含 DB 集成测试）；前端无改动。
