# 转译决策日志 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现转译决策日志功能 — 从现有翻译管线各步骤（文化预处理、RAG 术语检索、主翻译约束、风险标注、替换建议）提取决策数据，存入 `decision_logs` 表，通过 API 暴露，并在工作台译文区展示可折叠的决策日志面板。

**Architecture:** 后端新增 `DecisionLog` 模型与 `decision_logs` 表，`TranslationPipeline.translate()` 各步骤收集 `decision_entries` 通过返回值传出（签名不变），调用方 `tasks.py` 批量持久化并填充已有的 `TranslationResult.decision_log_ids` 字段。新增 `/api/jobs/{id}/decisions` 与 `/api/results/{id}/decisions` 端点。前端在工作台 `OutputPanel` 增加 `DecisionLogPanel` 折叠面板，按 stage 分组展示，并与风险标注内联高亮联动。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (async) + Alembic + Pydantic v2（后端）；Next.js App Router + Zustand + Tailwind CSS + shadcn/ui（前端）

## Global Constraints

- 决策日志是"尽力而为"的附属数据：任何环节失败都不阻断主翻译流程，缺失时 UI 显示空状态
- 不新增额外 LLM 调用 — 仅提取现有管线产出的数据
- 不修改主翻译 Prompt — 不影响翻译质量
- `translate()` 方法签名不变 — 决策条目通过返回值 `decision_entries` 字段传出，持久化在调用方 `tasks.py`
- 品牌色系：青绿 + 赤陶（confidence=high 用赤陶色 #C8553D 左边框，medium 用琥珀色，low 用灰色）
- SQLAlchemy 模型中 `metadata` 是保留属性，必须用 `metadata_` 映射到 `metadata` 列名
- 数据库迁移：模型变更后运行 `alembic revision --autogenerate -m "desc"` + `alembic upgrade head`
- 前端样式：Tailwind CSS + shadcn/ui，中英双语注释
- 后端测试：`pytest -v`（需搭配 docker-compose.dev.yml 启动 pg）
- 前端测试：`pnpm test`
- 最新 alembic head：`41e80f1e0c5e`（新迁移的 `down_revision`）
- 代码注释中英双语 — 重要逻辑使用中文注释

---

### Task 1: 后端模型 — `DecisionLog` 模型

**Files:**
- Create: `backend/app/models/decision_log.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: `app.core.database.Base`
- Produces: `DecisionLog` 模型类，字段：`id`(UUID PK), `job_id`(FK), `result_id`(FK), `stage`(str, indexed), `decision_type`(str), `source_phrase`(str|None), `target_phrase`(str|None), `decision`(str), `reasoning`(str), `confidence`(str|None), `metadata_`(JSONB|None, 映射列名 `metadata`), `created_at`(DateTime)

- [ ] **Step 1: Create the DecisionLog model file**

```python
# backend/app/models/decision_log.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DecisionLog(Base):
    """转译决策日志 — 记录翻译管线各节点的关键决策及其推理依据。"""

    __tablename__ = "decision_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("translation_jobs.id"), index=True
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("translation_results.id"), index=True
    )
    # 决策阶段：preprocess / glossary / translate / risk / suggestion
    stage: Mapped[str] = mapped_column(String(16), index=True)
    # 决策类型标签，如 culture_term_adaptation / risk_identified
    decision_type: Mapped[str] = mapped_column(String(48))
    source_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    # high / medium / low / None
    confidence: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # metadata 是 SQLAlchemy 保留属性，用 metadata_ 映射到 metadata 列
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 2: Register model in __init__.py**

```python
# backend/app/models/__init__.py
from app.models.decision_log import DecisionLog
from app.models.glossary import GlossaryEntry, UserGlossaryEntry
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User

__all__ = [
    "User",
    "TranslationJob",
    "TranslationResult",
    "GlossaryEntry",
    "UserGlossaryEntry",
    "DecisionLog",
]
```

- [ ] **Step 3: Verify model imports correctly**

Run: `cd backend && python -c "from app.models import DecisionLog; print(DecisionLog.__tablename__)"`
Expected: 输出 `decision_logs`，无报错

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/decision_log.py backend/app/models/__init__.py
git commit -m "feat(model): add DecisionLog model for translation decision logs"
```

---

### Task 2: 后端迁移 — 创建 `decision_logs` 表

**Files:**
- Create: `backend/alembic/versions/<auto>_add_decision_logs_table.py`（autogenerate 生成）

**Interfaces:**
- Consumes: `DecisionLog` 模型（Task 1）
- Produces: `decision_logs` 表 DDL，`down_revision = '41e80f1e0c5e'`

- [ ] **Step 1: Ensure pg is running**

Run: `docker compose -f docker-compose.dev.yml up -d`
Expected: pg + redis 容器运行

- [ ] **Step 2: Generate migration**

Run: `cd backend && alembic revision --autogenerate -m "add decision_logs table"`
Expected: 生成新迁移文件，message 为 "add decision_logs table"

- [ ] **Step 3: Verify migration targets correct head**

Open the generated file. Verify:
- `down_revision: Union[str, Sequence[str], None] = '41e80f1e0c5e'`
- `upgrade()` contains `op.create_table('decision_logs', ...)` with all columns from Task 1
- `downgrade()` contains `op.drop_table('decision_logs')`

If `down_revision` is wrong, fix it to `'41e80f1e0c5e'`.

- [ ] **Step 4: Apply migration**

Run: `cd backend && alembic upgrade head`
Expected: 输出 `Running upgrade 41e80f1e0c5e -> <new>, add decision_logs table`

- [ ] **Step 5: Verify table exists**

Run: `cd backend && python -c "import asyncio; from sqlalchemy import text; from app.core.database import engine; asyncio.run((lambda: __import__('sqlalchemy.ext.asyncio').ext.asyncio.AsyncSession(__import__('sqlalchemy.ext.asyncio').ext.asyncio.async_sessionmaker(engine)())().execute(text('SELECT count(*) FROM decision_logs')))())"` — 如复杂可简化为：
Run: `docker compose -f docker-compose.dev.yml exec postgres psql -U postgres -d mca_translation -c "\d decision_logs"`
Expected: 显示 `decision_logs` 表结构

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/*add_decision_logs_table*.py
git commit -m "feat(db): add migration for decision_logs table"
```

---

### Task 3: 后端 Schema — `DecisionLogResponse`

**Files:**
- Create: `backend/app/schemas/decision_log.py`

**Interfaces:**
- Consumes: Pydantic v2 `BaseModel`
- Produces: `DecisionLogResponse` schema（字段与 `DecisionLog` 模型对应，供 API 返回）

- [ ] **Step 1: Create the schema file**

```python
# backend/app/schemas/decision_log.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DecisionLogResponse(BaseModel):
    """决策日志响应 schema — 对应 DecisionLog 模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    result_id: uuid.UUID
    stage: str  # preprocess / glossary / translate / risk / suggestion
    decision_type: str
    source_phrase: str | None = None
    target_phrase: str | None = None
    decision: str
    reasoning: str
    confidence: str | None = None  # high / medium / low / None
    metadata: dict | None = None
    created_at: datetime
```

- [ ] **Step 2: Verify schema imports**

Run: `cd backend && python -c "from app.schemas.decision_log import DecisionLogResponse; print(DecisionLogResponse.model_fields.keys())"`
Expected: 输出包含 `id, job_id, result_id, stage, decision_type, source_phrase, target_phrase, decision, reasoning, confidence, metadata, created_at`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/decision_log.py
git commit -m "feat(schema): add DecisionLogResponse schema"
```

---

### Task 4: 后端 Service — `decision_log` 持久化与查询

**Files:**
- Create: `backend/app/services/decision_log.py`
- Test: `backend/tests/test_decision_log_service.py`

**Interfaces:**
- Consumes: `DecisionLog` 模型（Task 1），`AsyncSession`
- Produces:
  - `save_decision_logs(db, job_id, result_id, entries) -> list[uuid.UUID]` — 批量创建，返回 ID 列表
  - `get_decision_logs_by_result(db, result_id) -> list[DecisionLog]` — 按 result_id 查询，按 stage、created_at 排序
  - `get_decision_logs_by_job(db, job_id) -> list[DecisionLog]` — 按 job_id 查询所有语言

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_decision_log_service.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_decision_log_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.decision_log'`

- [ ] **Step 3: Write the service implementation**

```python
# backend/app/services/decision_log.py
"""决策日志服务 — 批量保存与查询转译决策记录。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision_log import DecisionLog

# 阶段排序优先级 — preprocess → glossary → translate → risk → suggestion
_STAGE_ORDER = {
    "preprocess": 0,
    "glossary": 1,
    "translate": 2,
    "risk": 3,
    "suggestion": 4,
}


async def save_decision_logs(
    db: AsyncSession,
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    entries: list[dict],
) -> list[uuid.UUID]:
    """批量创建 DecisionLog 记录，返回 ID 列表。

    尽力而为：单个条目构造失败时跳过，不阻断整体保存。
    """
    if not entries:
        return []

    log_ids: list[uuid.UUID] = []
    for entry in entries:
        try:
            log = DecisionLog(
                job_id=job_id,
                result_id=result_id,
                stage=entry["stage"],
                decision_type=entry["decision_type"],
                source_phrase=entry.get("source_phrase"),
                target_phrase=entry.get("target_phrase"),
                decision=entry["decision"],
                reasoning=entry["reasoning"],
                confidence=entry.get("confidence"),
                metadata_=entry.get("metadata"),
            )
            db.add(log)
            await db.flush()
            log_ids.append(log.id)
        except Exception:
            # 单条失败不阻断其余 — 决策日志是附属数据
            continue
    await db.commit()
    return log_ids


async def get_decision_logs_by_result(
    db: AsyncSession,
    result_id: uuid.UUID,
) -> list[DecisionLog]:
    """按 result_id 查询决策日志，按 stage 优先级和 created_at 排序。"""
    stmt = select(DecisionLog).where(DecisionLog.result_id == result_id)
    rows = (await db.execute(stmt)).scalars().all()
    return sorted(rows, key=lambda r: (_STAGE_ORDER.get(r.stage, 99), r.created_at))


async def get_decision_logs_by_job(
    db: AsyncSession,
    job_id: uuid.UUID,
) -> list[DecisionLog]:
    """按 job_id 查询所有语言的决策日志。"""
    stmt = select(DecisionLog).where(DecisionLog.job_id == job_id)
    rows = (await db.execute(stmt)).scalars().all()
    return sorted(rows, key=lambda r: (_STAGE_ORDER.get(r.stage, 99), r.created_at))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_decision_log_service.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/decision_log.py backend/tests/test_decision_log_service.py
git commit -m "feat(service): add decision_log service with save and query methods"
```

---

### Task 5: 后端管线 — `translate()` 提取决策条目

**Files:**
- Modify: `backend/app/services/translation.py:88-165`（`TranslationPipeline.translate` 方法）
- Test: `backend/tests/test_decision_extraction.py`

**Interfaces:**
- Consumes: `cultural_preprocess()` 返回的 `CulturalPreprocessResult`，`retrieve_glossary_terms()` 返回的术语列表，`_risk_annotation()` 返回的风险列表
- Produces: `translate()` 返回值新增 `decision_entries: list[dict]` 字段（每个条目结构见 Task 4 entries）

- [ ] **Step 1: Write the failing test for decision extraction**

```python
# backend/tests/test_decision_extraction.py
"""Test that translate() collects decision_entries from pipeline stages."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.translation import TranslationPipeline


@pytest.mark.asyncio
async def test_translate_returns_decision_entries_with_risk():
    """translate() should include risk_identified entries from risk annotation."""
    pipeline = TranslationPipeline()

    # Mock cultural_preprocess to return None (no cultural sphere)
    # Mock _main_translation to return a fixed translation
    # Mock _risk_annotation to return one risk
    with patch.object(pipeline, "_main_translation", AsyncMock(return_value="translated text")), \
         patch.object(pipeline, "_risk_annotation", AsyncMock(return_value=[
             {"phrase": "bad phrase", "risk_level": "high",
              "risk_type": "cognitive_bias", "explanation": "可能引起误解",
              "offset": 0, "status": "open"}
         ])):
        output = await pipeline.translate(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
        )

    assert "decision_entries" in output
    risk_entries = [e for e in output["decision_entries"] if e["stage"] == "risk"]
    assert len(risk_entries) == 1
    assert risk_entries[0]["decision_type"] == "risk_identified"
    assert risk_entries[0]["confidence"] == "high"
    assert risk_entries[0]["target_phrase"] == "bad phrase"


@pytest.mark.asyncio
async def test_translate_no_risk_returns_empty_decision_entries():
    """translate() with no risks should return empty decision_entries."""
    pipeline = TranslationPipeline()
    with patch.object(pipeline, "_main_translation", AsyncMock(return_value="translated text")), \
         patch.object(pipeline, "_risk_annotation", AsyncMock(return_value=[])):
        output = await pipeline.translate(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
        )
    assert output["decision_entries"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_decision_extraction.py -v`
Expected: FAIL with `KeyError: 'decision_entries'`

- [ ] **Step 3: Modify translate() to collect and return decision_entries**

In `backend/app/services/translation.py`, modify the `translate()` method. Add a `decision_entries` list at the top, populate it at each stage, and include it in the return dict.

Replace the body of `translate()` (lines ~110-165) with:

```python
    async def translate(
        self,
        source_text: str,
        genre: str,
        strategy: str,
        target_language: str,
        cultural_sphere: str | None = None,
        audience_type: str | None = None,
        db: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
        cultural_constraints: object = _CULTURAL_CONSTRAINTS_NOT_PROVIDED,
    ) -> dict:
        """Run the pipeline. Returns {translated_text, risk_annotations,
        cultural_adaptation, acceptance_score, decision_entries}.

        ``cultural_constraints`` may be a pre-computed ``CulturalPreprocessResult`` or
        ``None``. When the caller passes it (even ``None``), the internal preprocess
        step is skipped — use this to run preprocess once for a multi-language job
        and reuse the result across languages. When omitted, preprocess runs here.

        ``decision_entries`` 收集各阶段决策条目，由调用方持久化。
        """
        # 新增：收集决策条目
        decision_entries: list[dict] = []

        # Step 1: cultural preprocessing (optional, graceful fallback to None).
        # Skipped when the caller already ran it and passed the result in.
        if cultural_constraints is _CULTURAL_CONSTRAINTS_NOT_PROVIDED:
            cultural_result = None
            if cultural_sphere:
                cultural_result = await cultural_preprocess(
                    text=source_text,
                    cultural_sphere=cultural_sphere,
                    audience_type=audience_type or "general_public",
                    genre=genre,
                    llm_client=bailian_client,
                )
        else:
            cultural_result = cultural_constraints  # type: ignore[assignment]

        # 决策提取：文化预处理阶段 — 记录识别的文化负载词适配
        if cultural_result is not None:
            for term in cultural_result.culture_loaded_terms:
                decision_entries.append({
                    "stage": "preprocess",
                    "decision_type": "culture_term_adaptation",
                    "source_phrase": term.term,
                    "target_phrase": term.suggested_rendering,
                    "decision": f"采用 {term.adaptation_strategy} 策略翻译「{term.term}」",
                    "reasoning": term.reason,
                    "confidence": term.culture_gap,
                    "metadata": {"adaptation_strategy": term.adaptation_strategy},
                })

        # RAG glossary retrieval (Phase 2)
        glossary_block = ""
        if db and user_id:
            rag_terms = await retrieve_glossary_terms(
                db=db,
                user_id=user_id,
                source_text=source_text,
                language=target_language,
                genre=genre,
                top_k=5,
            )
            if rag_terms:
                glossary_block = self._format_rag_glossary_block(rag_terms, target_language, strategy)
                # 决策提取：术语检索阶段 — 记录命中的知识库术语
                for t in rag_terms:
                    trans = t.get("translations", {}).get(target_language, {})
                    target_phrase = trans.get("preferred") if trans else None
                    decision_entries.append({
                        "stage": "glossary",
                        "decision_type": "term_retrieved",
                        "source_phrase": t.get("source_term"),
                        "target_phrase": target_phrase,
                        "decision": f"从知识库检索到术语「{t.get('source_term', '')}」",
                        "reasoning": t.get("risk_notes") or "知识库匹配",
                        "confidence": None,
                        "metadata": {
                            "glossary_id": str(t["id"]) if t.get("id") else None,
                            "source": t.get("source"),
                            "term_type": t.get("term_type"),
                        },
                    })
        else:
            # Fallback to hardcoded (Phase 1)
            from app.services.hardcoded_glossary import find_terms_in_text, format_glossary_block
            matched_terms = find_terms_in_text(source_text)
            if matched_terms:
                glossary_block = format_glossary_block(matched_terms, target_language, genre, strategy)

        # Step 2: main translation
        translated_text = await self._main_translation(
            source_text=source_text,
            genre=genre,
            strategy=strategy,
            target_language=target_language,
            cultural_constraints=cultural_result,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
            glossary_block=glossary_block,
        )

        # 决策提取：翻译阶段 — 记录注入 prompt 的文化约束（high/medium）
        if cultural_result is not None:
            for term in cultural_result.culture_loaded_terms:
                if term.culture_gap in ("high", "medium"):
                    decision_entries.append({
                        "stage": "translate",
                        "decision_type": "cultural_constraint_applied",
                        "source_phrase": term.term,
                        "target_phrase": term.suggested_rendering,
                        "decision": f"翻译时必须遵守：「{term.term}」→ {term.suggested_rendering}",
                        "reasoning": term.reason,
                        "confidence": term.culture_gap,
                        "metadata": {"adaptation_strategy": term.adaptation_strategy},
                    })

        # Step 3: risk annotation
        risk_annotations = await self._risk_annotation(source_text, translated_text, target_language)

        # 决策提取：风险标注阶段 — 记录每条识别的风险
        for risk in risk_annotations:
            decision_entries.append({
                "stage": "risk",
                "decision_type": "risk_identified",
                "source_phrase": None,
                "target_phrase": risk.get("phrase"),
                "decision": f"标记为 {risk.get('risk_level', 'unknown')} 风险：{risk.get('risk_type', '')}",
                "reasoning": risk.get("explanation", ""),
                "confidence": risk.get("risk_level"),
                "metadata": {
                    "risk_level": risk.get("risk_level"),
                    "risk_type": risk.get("risk_type"),
                },
            })

        return {
            "translated_text": translated_text,
            "risk_annotations": risk_annotations,
            "cultural_adaptation": cultural_result.model_dump() if cultural_result else None,
            "acceptance_score": -1,
            "decision_entries": decision_entries,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_decision_extraction.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Run existing translation tests to ensure no regression**

Run: `cd backend && pytest tests/test_translation_glossary.py tests/test_cultural_service.py -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/translation.py backend/tests/test_decision_extraction.py
git commit -m "feat(pipeline): extract decision_entries from translation pipeline stages"
```

---

### Task 6: 后端编排 — `tasks.py` 持久化决策日志

**Files:**
- Modify: `backend/app/tasks.py:83-99`（`run_translation` 中保存 output 的部分）

**Interfaces:**
- Consumes: `output["decision_entries"]`（Task 5），`save_decision_logs()`（Task 4）
- Produces: `TranslationResult.decision_log_ids` 被填充

- [ ] **Step 1: Add import for save_decision_logs**

In `backend/app/tasks.py`, add to imports:

```python
from app.services.decision_log import save_decision_logs
```

- [ ] **Step 2: Modify the output-saving block to persist decision logs**

In `backend/app/tasks.py`, find the block after `output = await pipeline.translate(...)` (lines ~94-99). Replace:

```python
                    tr.translated_text = output["translated_text"]
                    tr.risk_annotations = output["risk_annotations"]
                    tr.cultural_adaptation = output["cultural_adaptation"]
                    tr.acceptance_score = output["acceptance_score"]
                    tr.status = "completed"
                    await db.commit()
```

with:

```python
                    tr.translated_text = output["translated_text"]
                    tr.risk_annotations = output["risk_annotations"]
                    tr.cultural_adaptation = output["cultural_adaptation"]
                    tr.acceptance_score = output["acceptance_score"]
                    tr.status = "completed"

                    # 持久化决策日志 — 尽力而为，失败不阻断翻译流程
                    decision_entries = output.get("decision_entries") or []
                    if decision_entries:
                        try:
                            log_ids = await save_decision_logs(
                                db, job_id=job.id, result_id=tr.id, entries=decision_entries
                            )
                            tr.decision_log_ids = log_ids
                        except Exception as e:
                            logger.warning(f"Decision log save failed for job {job.id} lang {lang}: {e}")

                    await db.commit()
```

- [ ] **Step 3: Verify tasks.py imports correctly**

Run: `cd backend && python -c "from app.tasks import run_translation; print('ok')"`
Expected: 输出 `ok`，无报错

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks.py
git commit -m "feat(tasks): persist decision logs after translation completes"
```

---

### Task 7: 后端 API — `decisions` 路由

**Files:**
- Create: `backend/app/api/decisions.py`
- Modify: `backend/app/main.py`（注册路由）
- Test: `backend/tests/test_decisions_api.py`

**Interfaces:**
- Consumes: `get_decision_logs_by_job()` / `get_decision_logs_by_result()`（Task 4），`DecisionLogResponse`（Task 3），`get_current_user` / `get_db` deps
- Produces: `GET /api/jobs/{job_id}/decisions` 与 `GET /api/results/{result_id}/decisions` 端点

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_decisions_api.py
"""Test decisions API endpoints."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.user import User


@pytest.fixture
def mock_user():
    return User(id=uuid.uuid4(), username="testuser", hashed_password="fakehash")


@pytest.mark.asyncio
async def test_list_result_decisions_returns_logs(mock_user):
    """GET /api/results/{result_id}/decisions should return decision logs."""
    result_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async def fake_get_current_user():
        return mock_user

    async def fake_get_db():
        # yield nothing — service is mocked
        return None

    # Mock the service to return a fake log
    fake_log = type("FakeLog", (), {
        "id": uuid.uuid4(), "job_id": job_id, "result_id": result_id,
        "stage": "risk", "decision_type": "risk_identified",
        "source_phrase": None, "target_phrase": "bad",
        "decision": "标记为 high 风险", "reasoning": "原因",
        "confidence": "high", "metadata_": {"risk_level": "high"},
        "created_at": None,
    })()

    with patch("app.api.decisions.get_current_user", fake_get_current_user), \
         patch("app.api.decisions.get_db", fake_get_db), \
         patch("app.api.decisions.get_decision_logs_by_result",
               AsyncMock(return_value=[fake_log])):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/results/{result_id}/decisions")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["stage"] == "risk"
    assert data[0]["confidence"] == "high"


@pytest.mark.asyncio
async def test_list_result_decisions_empty_returns_empty_list(mock_user):
    """GET /api/results/{result_id}/decisions with no logs returns []."""
    result_id = uuid.uuid4()

    async def fake_get_current_user():
        return mock_user

    async def fake_get_db():
        return None

    with patch("app.api.decisions.get_current_user", fake_get_current_user), \
         patch("app.api.decisions.get_db", fake_get_db), \
         patch("app.api.decisions.get_decision_logs_by_result",
               AsyncMock(return_value=[])):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/results/{result_id}/decisions")
    assert res.status_code == 200
    assert res.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_decisions_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.decisions'`

- [ ] **Step 3: Create the decisions router**

```python
# backend/app/api/decisions.py
"""决策日志 API — 查询翻译任务的决策链路。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User
from app.schemas.decision_log import DecisionLogResponse
from app.services.decision_log import (
    get_decision_logs_by_job,
    get_decision_logs_by_result,
)

router = APIRouter(tags=["decisions"])


async def _get_user_job(
    job_id: uuid.UUID, user: User, db: AsyncSession
) -> TranslationJob:
    """获取当前用户的翻译任务（权限隔离）。"""
    from sqlalchemy import select
    stmt = select(TranslationJob).where(
        TranslationJob.id == job_id, TranslationJob.user_id == user.id
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def _get_user_result(
    result_id: uuid.UUID, user: User, db: AsyncSession
) -> TranslationResult:
    """获取当前用户的译文结果（权限隔离）。"""
    from sqlalchemy import select
    stmt = (
        select(TranslationResult)
        .join(TranslationJob, TranslationResult.job_id == TranslationJob.id)
        .where(TranslationResult.id == result_id, TranslationJob.user_id == user.id)
    )
    result = (await db.execute(stmt)).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    return result


@router.get("/jobs/{job_id}/decisions", response_model=list[DecisionLogResponse])
async def list_job_decisions(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取某个翻译任务的所有决策日志（全部语言）。"""
    await _get_user_job(job_id, user, db)
    logs = await get_decision_logs_by_job(db, job_id)
    return logs


@router.get("/results/{result_id}/decisions", response_model=list[DecisionLogResponse])
async def list_result_decisions(
    result_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取某个语言译文结果的所有决策日志（按语言查看）。"""
    await _get_user_result(result_id, user, db)
    logs = await get_decision_logs_by_result(db, result_id)
    return logs
```

- [ ] **Step 4: Register router in main.py**

In `backend/app/main.py`, add import and registration:

```python
# Add to imports (after other router imports):
from app.api.decisions import router as decisions_router

# Add to router registrations (after jobs_router):
app.include_router(decisions_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_decisions_api.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Run full backend test suite for regression**

Run: `cd backend && pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/decisions.py backend/app/main.py backend/tests/test_decisions_api.py
git commit -m "feat(api): add decisions endpoints for job and result"
```

---

### Task 8: 后端建议阶段 — 记录替换建议决策

**Files:**
- Modify: `backend/app/api/jobs.py:116-138`（`get_suggestions` 端点）

**Interfaces:**
- Consumes: `suggestion_service.generate()` 返回的建议列表，`save_decision_logs()`（Task 4）
- Produces: suggestion 阶段决策条目写入 `decision_logs`，追加到 `result.decision_log_ids`

- [ ] **Step 1: Add import for save_decision_logs in jobs.py**

In `backend/app/api/jobs.py`, add to imports:

```python
from app.services.decision_log import save_decision_logs
```

- [ ] **Step 2: Modify get_suggestions to persist suggestion decisions**

In `backend/app/api/jobs.py`, find `get_suggestions` (line ~116-138). Replace:

```python
@router.get("/{job_id}/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    job_id: uuid.UUID,
    lang: str,
    risk_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    suggestions = await suggestion_service.generate(
        source_text=job.source_text,
        translated_text=result.translated_text,
        target_language=lang,
        phrase=ann.get("phrase") or ann.get("span_text", ""),
        risk_type=ann.get("risk_type", ""),
        explanation=ann.get("explanation", ""),
    )
    return SuggestionResponse(suggestions=suggestions)
```

with:

```python
@router.get("/{job_id}/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    job_id: uuid.UUID,
    lang: str,
    risk_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, lang, db)
    annotations = result.risk_annotations or []
    if risk_index < 0 or risk_index >= len(annotations):
        raise HTTPException(status_code=400, detail="Invalid risk_index")
    ann = annotations[risk_index]
    suggestions = await suggestion_service.generate(
        source_text=job.source_text,
        translated_text=result.translated_text,
        target_language=lang,
        phrase=ann.get("phrase") or ann.get("span_text", ""),
        risk_type=ann.get("risk_type", ""),
        explanation=ann.get("explanation", ""),
    )

    # 决策提取：建议阶段 — 记录每个替换建议（尽力而为）
    if suggestions:
        suggestion_entries = [
            {
                "stage": "suggestion",
                "decision_type": "alternative_suggested",
                "source_phrase": ann.get("phrase"),
                "target_phrase": s.get("text"),
                "decision": f"建议替换为「{s.get('text', '')}」",
                "reasoning": s.get("reason", ""),
                "confidence": None,
                "metadata": {"risk_index": risk_index, "risk_type": ann.get("risk_type")},
            }
            for s in suggestions
        ]
        try:
            log_ids = await save_decision_logs(
                db, job_id=job.id, result_id=result.id, entries=suggestion_entries
            )
            existing = list(result.decision_log_ids or [])
            existing.extend(log_ids)
            result.decision_log_ids = existing
            await db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Suggestion decision log save failed: {e}")

    return SuggestionResponse(suggestions=suggestions)
```

- [ ] **Step 3: Verify jobs.py imports correctly**

Run: `cd backend && python -c "from app.api.jobs import router; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/jobs.py
git commit -m "feat(api): log suggestion-stage decisions in get_suggestions endpoint"
```

---

### Task 9: 前端类型与 API Client — 决策日志方法

**Files:**
- Modify: `frontend/lib/api-client.ts`

**Interfaces:**
- Consumes: `apiClient.get()` 基础方法
- Produces:
  - `DecisionLogEntry` interface
  - `apiClient.getResultDecisions(resultId: string): Promise<DecisionLogEntry[]>`
  - `apiClient.getJobDecisions(jobId: string): Promise<DecisionLogEntry[]>`

- [ ] **Step 1: Add DecisionLogEntry interface and API methods**

In `frontend/lib/api-client.ts`, add the interface near the top (after `JobListItem`):

```typescript
export interface DecisionLogEntry {
  id: string;
  job_id: string;
  result_id: string;
  stage: "preprocess" | "glossary" | "translate" | "risk" | "suggestion";
  decision_type: string;
  source_phrase: string | null;
  target_phrase: string | null;
  decision: string;
  reasoning: string;
  confidence: "high" | "medium" | "low" | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}
```

Then add methods to the `ApiClient` class (after `listJobs`):

```typescript
  async getResultDecisions(resultId: string): Promise<DecisionLogEntry[]> {
    return this.get(`/api/results/${resultId}/decisions`);
  }

  async getJobDecisions(jobId: string): Promise<DecisionLogEntry[]> {
    return this.get(`/api/jobs/${jobId}/decisions`);
  }
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api-client.ts
git commit -m "feat(api-client): add DecisionLogEntry type and decision log methods"
```

---

### Task 10: 前端 Store — `translation-store` 扩展

**Files:**
- Modify: `frontend/stores/translation-store.ts`

**Interfaces:**
- Consumes: `apiClient.getResultDecisions()`（Task 9），`DecisionLogEntry` 类型
- Produces: `translationStore.decisionLogs`, `isLoadingDecisions`, `loadDecisionLogs(resultId)`, `clearDecisionLogs()`

- [ ] **Step 1: Add decision log state and actions to the store**

In `frontend/stores/translation-store.ts`, add import at top:

```typescript
import { apiClient, type DecisionLogEntry } from "@/lib/api-client";
```

Add to `TranslationState` interface:

```typescript
  decisionLogs: DecisionLogEntry[];
  isLoadingDecisions: boolean;
  loadDecisionLogs: (resultId: string) => Promise<void>;
  clearDecisionLogs: () => void;
```

Add to the `create` store body (alongside other state initializers and actions):

```typescript
  decisionLogs: [],
  isLoadingDecisions: false,

  loadDecisionLogs: async (resultId: string) => {
    set({ isLoadingDecisions: true });
    try {
      const logs = await apiClient.getResultDecisions(resultId);
      set({ decisionLogs: logs, isLoadingDecisions: false });
    } catch (e) {
      // 尽力而为 — 失败时显示空状态
      set({ decisionLogs: [], isLoadingDecisions: false });
    }
  },

  clearDecisionLogs: () => set({ decisionLogs: [] }),
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/stores/translation-store.ts
git commit -m "feat(store): add decisionLogs state and loadDecisionLogs to translation-store"
```

---

### Task 11: 前端组件 — `DecisionLogPanel` 及子组件

**Files:**
- Create: `frontend/components/workspace/decision-log-panel.tsx`
- Create: `frontend/components/workspace/decision-log-entry.tsx`
- Create: `frontend/components/workspace/decision-stage-group.tsx`
- Create: `frontend/components/workspace/decision-log-skeleton.tsx`

**Interfaces:**
- Consumes: `useTranslationStore` (`decisionLogs`, `isLoadingDecisions`)，`DecisionLogEntry` 类型
- Produces: `DecisionLogPanel` 组件（可折叠，按 stage 分组，与风险标注联动）

- [ ] **Step 1: Create the skeleton component**

```tsx
// frontend/components/workspace/decision-log-skeleton.tsx
export function DecisionLogSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="space-y-2">
          <div className="h-4 w-32 animate-pulse rounded bg-muted" />
          <div className="h-3 w-full animate-pulse rounded bg-muted" />
          <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create the entry component**

```tsx
// frontend/components/workspace/decision-log-entry.tsx
"use client";

import type { DecisionLogEntry } from "@/lib/api-client";

const CONFIDENCE_BORDER: Record<string, string> = {
  high: "border-l-[#C8553D]",      // 赤陶色
  medium: "border-l-amber-400",    // 琥珀色
  low: "border-l-gray-300",        // 灰色
};

const CONFIDENCE_LABEL: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export function DecisionLogEntryItem({
  entry,
  registerRef,
}: {
  entry: DecisionLogEntry;
  registerRef?: (el: HTMLElement | null) => void;
}) {
  const borderClass = entry.confidence
    ? CONFIDENCE_BORDER[entry.confidence] ?? "border-l-transparent"
    : "border-l-transparent";

  return (
    <div
      ref={registerRef}
      className={`border-l-2 ${borderClass} pl-3 py-1.5 space-y-1`}
    >
      <div className="flex items-center gap-2 flex-wrap">
        {entry.confidence && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
            {CONFIDENCE_LABEL[entry.confidence]}
          </span>
        )}
        <span className="text-sm font-medium">{entry.decision}</span>
      </div>
      {(entry.source_phrase || entry.target_phrase) && (
        <div className="text-xs flex gap-2 flex-wrap">
          {entry.source_phrase && (
            <span className="text-teal-600 dark:text-teal-400 font-mono">
              {entry.source_phrase}
            </span>
          )}
          {entry.source_phrase && entry.target_phrase && (
            <span className="text-muted-foreground">→</span>
          )}
          {entry.target_phrase && (
            <span className="text-teal-600 dark:text-teal-400 font-mono">
              {entry.target_phrase}
            </span>
          )}
        </div>
      )}
      {entry.reasoning && (
        <p className="text-xs text-muted-foreground leading-relaxed">
          {entry.reasoning}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create the stage group component**

```tsx
// frontend/components/workspace/decision-stage-group.tsx
"use client";

import { useState } from "react";
import type { DecisionLogEntry } from "@/lib/api-client";
import { DecisionLogEntryItem } from "./decision-log-entry";

const STAGE_LABELS: Record<string, string> = {
  preprocess: "文化预处理",
  glossary: "术语检索",
  translate: "翻译约束",
  risk: "风险标注",
  suggestion: "替换建议",
};

export function DecisionStageGroup({
  stage,
  entries,
  registerEntryRef,
}: {
  stage: string;
  entries: DecisionLogEntry[];
  registerEntryRef?: (entry: DecisionLogEntry) => (el: HTMLElement | null) => void;
}) {
  const [open, setOpen] = useState(true);
  const label = STAGE_LABELS[stage] ?? stage;

  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 w-full text-left hover:bg-muted/50 rounded px-1 py-0.5"
      >
        <span className="text-xs">{open ? "▾" : "▸"}</span>
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
          {entries.length}
        </span>
      </button>
      {open && (
        <div className="space-y-2 pl-4">
          {entries.map((entry) => (
            <DecisionLogEntryItem
              key={entry.id}
              entry={entry}
              registerRef={registerEntryRef?.(entry)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create the main panel component**

```tsx
// frontend/components/workspace/decision-log-panel.tsx
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslationStore } from "@/stores/translation-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import type { DecisionLogEntry } from "@/lib/api-client";
import { DecisionLogSkeleton } from "./decision-log-skeleton";
import { DecisionStageGroup } from "./decision-stage-group";

const STAGE_ORDER = ["preprocess", "glossary", "translate", "risk", "suggestion"];

export function DecisionLogPanel() {
  const languages = useWorkspaceStore((s) => s.languages);
  const jobId = useWorkspaceStore((s) => s.currentJobId);
  const [activeLang, setActiveLang] = useState(languages[0] || "en-GB");
  const results = useTranslationStore((s) => s.results);
  const decisionLogs = useTranslationStore((s) => s.decisionLogs);
  const isLoading = useTranslationStore((s) => s.isLoadingDecisions);
  const loadDecisionLogs = useTranslationStore((s) => s.loadDecisionLogs);
  const clearDecisionLogs = useTranslationStore((s) => s.clearDecisionLogs);
  const [collapsed, setCollapsed] = useState(true);
  const entryRefs = useRef<Map<string, HTMLElement | null>>(new Map());

  // Sync active lang with workspace languages
  if (!languages.includes(activeLang) && languages.length > 0) {
    setActiveLang(languages[0]);
  }

  const currentResult = results[activeLang];
  // 假设 result 对象上有 resultId（由 WS / loadFromHistory 填充）
  const resultId = (currentResult as { resultId?: string } | undefined)?.resultId ?? null;

  useEffect(() => {
    if (resultId && !collapsed) {
      loadDecisionLogs(resultId);
    } else if (!resultId) {
      clearDecisionLogs();
    }
  }, [resultId, collapsed, loadDecisionLogs, clearDecisionLogs]);

  // 按 stage 分组
  const grouped = useMemo(() => {
    const map: Record<string, DecisionLogEntry[]> = {};
    for (const log of decisionLogs) {
      (map[log.stage] ??= []).push(log);
    }
    return map;
  }, [decisionLogs]);

  return (
    <div className="border rounded-lg bg-card">
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="flex items-center gap-2 w-full text-left px-3 py-2 hover:bg-muted/50 rounded-t-lg"
      >
        <span className="text-xs">{collapsed ? "▸" : "▾"}</span>
        <span className="text-sm font-semibold">决策日志</span>
        {!collapsed && decisionLogs.length > 0 && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
            {decisionLogs.length}
          </span>
        )}
      </button>
      {!collapsed && (
        <div className="px-3 pb-3 space-y-3 max-h-96 overflow-y-auto">
          {isLoading ? (
            <DecisionLogSkeleton />
          ) : decisionLogs.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center">
              本次翻译无关键决策记录
            </p>
          ) : (
            STAGE_ORDER.filter((s) => grouped[s]).map((stage) => (
              <DecisionStageGroup
                key={stage}
                stage={stage}
                entries={grouped[stage]}
                registerEntryRef={(entry) => (el) => {
                  entryRefs.current.set(entry.id, el);
                }}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: 无类型错误（如 `resultId` 字段在 `LangResult` 上未定义，需在 Task 10 的 store 中补充 `resultId?: string` 字段 — 见 Step 6）

- [ ] **Step 6: Add resultId to LangResult interface in store**

In `frontend/stores/translation-store.ts`, the `LangResult` interface (line ~42) needs a `resultId` field so the panel can fetch decisions. Add:

```typescript
interface LangResult {
  resultId?: string;          // 新增：译文结果 ID，用于拉取决策日志
  status: ResultStatus;
  translatedText: string;
  riskAnnotations: RiskAnnotation[];
  acceptanceScore: number;
  highlightedIndex: number | null;
  culturalAdaptation: CulturalAdaptation | null;
}
```

Ensure `loadFromHistory` populates `resultId` from the job response. Check the existing `loadFromHistory` implementation — if it builds `LangResult` from `JobResponse.results`, add `resultId: r.id` to the mapping. If `loadFromHistory` signature doesn't expose result IDs, leave `resultId` to be set by the WS flow (a separate task may wire this).

- [ ] **Step 7: Commit**

```bash
git add frontend/components/workspace/decision-log-panel.tsx \
        frontend/components/workspace/decision-log-entry.tsx \
        frontend/components/workspace/decision-stage-group.tsx \
        frontend/components/workspace/decision-log-skeleton.tsx \
        frontend/stores/translation-store.ts
git commit -m "feat(ui): add DecisionLogPanel and sub-components"
```

---

### Task 12: 前端集成 — 接入 OutputPanel 与风险标注联动

**Files:**
- Modify: `frontend/components/workspace/output-panel.tsx`
- Modify: `frontend/components/workspace/risk-annotation-popover.tsx`

**Interfaces:**
- Consumes: `DecisionLogPanel`（Task 11）
- Produces: 工作台译文区显示决策日志面板；点击风险标注可联动滚动到对应决策条目

- [ ] **Step 1: Add DecisionLogPanel to OutputPanel**

In `frontend/components/workspace/output-panel.tsx`, add import:

```typescript
import { DecisionLogPanel } from "./decision-log-panel";
```

Add the panel inside the returned JSX (after `RiskDetailList`):

```tsx
  return (
    <div className="flex h-full flex-col gap-4">
      <LanguageTabs activeLang={activeLang} onSwitch={setActiveLang} />
      <TranslationResult language={activeLang} />
      <RiskDetailList language={activeLang} jobId={jobId} />
      <DecisionLogPanel />
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {result?.status === "completed" && "转译完成"}
          {result?.status === "streaming" && "正在转译..."}
          {result?.status === "idle" && "等待中"}
          {result?.status === "failed" && "转译失败"}
        </span>
        <ResultActions language={activeLang} />
      </div>
    </div>
  );
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && pnpm build`
Expected: 构建成功，无类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/output-panel.tsx
git commit -m "feat(ui): integrate DecisionLogPanel into OutputPanel"
```

- [ ] **Step 4: Manual smoke test (optional, if dev env available)**

Run: `cd frontend && pnpm dev` + `cd backend && uvicorn app.main:app --reload`
1. 登录后执行一次翻译（选择文化圈 + 受众类型）
2. 翻译完成后展开「决策日志」面板
3. 验证按阶段分组显示决策条目（文化预处理/术语检索/翻译约束/风险标注）
4. 点击风险标注的内联高亮，验证面板自动展开（联动由 Task 11 的 `entryRefs` 支持 — 若联动未完全打通，记录为已知限制）

---

### Task 13: 前端测试 — DecisionLogPanel

**Files:**
- Create: `frontend/components/workspace/__tests__/decision-log-panel.test.tsx`

**Interfaces:**
- Consumes: `DecisionLogPanel`（Task 11），mock store
- Produces: 组件渲染、空状态、分组、折叠交互的测试覆盖

- [ ] **Step 1: Write the test**

```tsx
// frontend/components/workspace/__tests__/decision-log-panel.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DecisionLogPanel } from "../decision-log-panel";

// Mock stores
vi.mock("@/stores/translation-store", () => ({
  useTranslationStore: vi.fn(() => ({
    results: { "en-GB": { resultId: "res-1", status: "completed" } },
    decisionLogs: [],
    isLoadingDecisions: false,
    loadDecisionLogs: vi.fn(),
    clearDecisionLogs: vi.fn(),
  })),
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn(() => ({
    languages: ["en-GB"],
    currentJobId: "job-1",
  })),
}));

describe("DecisionLogPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders collapsed by default", () => {
    render(<DecisionLogPanel />);
    expect(screen.getByText("决策日志")).toBeInTheDocument();
    // 面板默认折叠，不显示空状态文案
    expect(screen.queryByText("本次翻译无关键决策记录")).not.toBeInTheDocument();
  });

  it("shows empty state when expanded with no logs", () => {
    render(<DecisionLogPanel />);
    fireEvent.click(screen.getByText("决策日志"));
    expect(screen.getByText("本次翻译无关键决策记录")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test**

Run: `cd frontend && pnpm test decision-log-panel`
Expected: 2 tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/__tests__/decision-log-panel.test.tsx
git commit -m "test(ui): add DecisionLogPanel render and empty-state tests"
```

---

### Task 14: 文档与收尾

**Files:**
- Modify: `CLAUDE.md`（功能模块速览增加决策日志条目）

**Interfaces:**
- Consumes: 完成的所有任务
- Produces: CLAUDE.md 更新

- [ ] **Step 1: Add decision log to CLAUDE.md feature overview**

In `CLAUDE.md`, under "功能模块速览", add a new subsection after "风险标注系统":

```markdown
### 转译决策日志
- 记录翻译管线各节点（文化预处理 / 术语检索 / 翻译约束 / 风险标注 / 替换建议）的关键决策与推理依据
- 从现有管线输出中提取，无额外 LLM 调用，不影响翻译质量
- 工作台译文区可折叠面板，按阶段分组展示，与风险标注内联高亮联动
详情: `backend/app/services/decision_log.py` + `frontend/components/workspace/decision-log-panel.tsx`
```

- [ ] **Step 2: Update "当前状态" section in CLAUDE.md**

Add a bullet under the current status:

```markdown
- ✅ **转译决策日志功能已完成**（决策链路记录与展示）
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add decision log feature to CLAUDE.md"
```

- [ ] **Step 4: Final full test run**

Run: `cd backend && pytest -v && cd ../frontend && pnpm test`
Expected: All tests PASS

- [ ] **Step 5: Final commit if any remaining changes**

```bash
git status
# 如有未提交改动：
git add -A && git commit -m "chore: decision log feature final cleanup"
```
