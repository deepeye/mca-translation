# translate 阶段流式输出（Level 1）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 translate 阶段用 qwen-max 流式输出，译文逐步出现在结果区（而非全程转圈），复用前端 2s 轮询与现有 streaming 渲染。

**Architecture:** `_main_translation` 把 `bailian_client.chat` 换成 `chat_stream`，累积 chunk 并经 `on_chunk` 回调把部分译文传回 Celery 任务；任务用 `make_chunk_writer` 节流（每 1s）把部分译文落库（状态保持 `streaming`），前端 2s 轮询拉到逐步增长的文本。`translate()` 仍返回最终 dict，risk 阶段不动。流式出错直接失败（丢弃部分译文 + failed + 退款）。

**Tech Stack:** FastAPI, Celery, SQLAlchemy 2.0 (async), 百炼 DashScope (qwen-max 流式), pytest, Next.js, TypeScript, Zustand, Vitest.

## Global Constraints

- 流式不降质：流式路径必须注入 glossary + cultural_constraints（与非流式同 prompt，复用 `build_translation_system_prompt` + `glossary_block`）。
- 流式出错直接失败：丢弃部分译文（`tr.translated_text = None`）+ `status=failed` + 退款，无回退、无重试。
- `chat_stream` 超时 180s（与 `chat` 一致）；不设 `max_tokens`。
- 节流 `STREAM_WRITE_INTERVAL = 1.0s`，`time.monotonic()` 计时，首个 chunk 立即写。
- 前端复用 2s 轮询与现有 streaming 渲染，仅加 `▍` 光标（Tailwind `animate-pulse`）；不改轮询间隔、不动 WS、不动 risk、不做多语言并发。
- 删除废弃 `translate_stream` 存根；其使用到的 import（`STRATEGY_DESCRIPTIONS`/`TRANSLATION_SYSTEM_PROMPT`/`language_descriptor`）仍被 `build_translation_system_prompt`/`_risk_annotation` 使用，**不移除**。
- 后端测试用 `pytest`（`@pytest.mark.asyncio`），mock `bailian_client`，不依赖 DB；前端 `pnpm test` 包装在此环境不可用（`[ERR_PNPM_IGNORED_BUILDS]`），用 `./node_modules/.bin/vitest run` 与 `./node_modules/.bin/tsc --noEmit`。
- main 分支开发，按任务频繁提交。

---

## File Structure

| 文件 | 动作 | 说明 |
|---|---|---|
| `backend/app/services/translation.py` | 修改 | `_main_translation` 流式 + `on_chunk`；`translate` 透传 `on_chunk`；删除 `translate_stream` |
| `backend/app/llm/bailian.py` | 修改 | `chat_stream` 超时 120s → 180s |
| `backend/tests/test_translation_streaming.py` | 创建 | `_main_translation` 流式/回调/质量对齐/错误传播 + `translate` 透传 |
| `backend/app/tasks.py` | 修改 | `make_chunk_writer` 节流 + 传 `on_chunk` + 失败丢弃部分译文 |
| `backend/tests/test_tasks_streaming.py` | 创建 | `make_chunk_writer` 节流单元测试 |
| `frontend/components/workspace/translation-result.tsx` | 修改 | streaming + 有文本时末尾加 `▍` 光标 |
| `frontend/components/workspace/__tests__/translation-result.test.tsx` | 创建 | streaming 光标渲染测试 |

---

### Task 1: `_main_translation` 流式 + `translate` 透传 + 删除 `translate_stream` + `chat_stream` 超时

**Files:**
- Modify: `backend/app/services/translation.py`
- Modify: `backend/app/llm/bailian.py`
- Test: `backend/tests/test_translation_streaming.py`（创建）

**Interfaces:**
- Consumes: `bailian_client.chat_stream(model, messages)`（async generator，yield content str）；`build_translation_system_prompt(...)`、`glossary_block`（不变）。
- Produces: `_main_translation(..., on_chunk: Callable[[str], Awaitable[None]] | None = None) -> str`（流式累积，返回完整译文）；`translate(..., on_chunk=None) -> dict`（透传 on_chunk，仍返回最终 dict）。Task 2 的 `make_chunk_writer` 产出符合 `on_chunk` 签名的闭包。

- [ ] **Step 1: 编写失败测试**

创建 `backend/tests/test_translation_streaming.py`：

```python
"""流式翻译单元测试：_main_translation 流式累积 + on_chunk 回调 + 质量对齐 + 错误传播。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.llm.bailian import bailian_client
from app.services.translation import TranslationPipeline


def _streaming(chunks):
    """构造伪 chat_stream：依次 yield chunks。"""
    async def fake_chat_stream(*, model, messages, temperature=0.3):
        for c in chunks:
            yield c
    return fake_chat_stream


@pytest.mark.asyncio
async def test_main_translation_streams_and_calls_on_chunk():
    pipeline = TranslationPipeline()
    received = []

    async def on_chunk(accumulated):
        received.append(accumulated)

    with patch.object(bailian_client, "chat_stream", _streaming(["Hello", " world"])):
        result = await pipeline._main_translation(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
            on_chunk=on_chunk,
        )

    assert result == "Hello world"
    assert received == ["Hello", "Hello world"]


@pytest.mark.asyncio
async def test_main_translation_injects_glossary_block_into_stream_prompt():
    pipeline = TranslationPipeline()
    captured = {}

    async def fake_chat_stream(*, model, messages, temperature=0.3):
        captured["system"] = messages[0]["content"]
        yield ""

    with patch.object(bailian_client, "chat_stream", fake_chat_stream):
        await pipeline._main_translation(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
            glossary_block="<glossary_terms>TERM</glossary_terms>",
        )

    assert "<glossary_terms>" in captured["system"]


@pytest.mark.asyncio
async def test_main_translation_propagates_stream_error():
    pipeline = TranslationPipeline()

    async def failing_stream(*, model, messages, temperature=0.3):
        raise RuntimeError("stream broke")
        yield ""  # noqa - 使其成为 async generator（raise 先于 yield 执行）

    with patch.object(bailian_client, "chat_stream", failing_stream):
        with pytest.raises(RuntimeError, match="stream broke"):
            await pipeline._main_translation(
                source_text="原文",
                genre="news",
                strategy="semantic_equivalence",
                target_language="en-GB",
            )


@pytest.mark.asyncio
async def test_translate_passes_on_chunk_to_main_translation():
    pipeline = TranslationPipeline()
    received = []

    async def on_chunk(accumulated):
        received.append(accumulated)

    with patch.object(bailian_client, "chat_stream", _streaming(["Hi", " there"])), \
         patch.object(pipeline, "_risk_annotation", AsyncMock(return_value=[])):
        output = await pipeline.translate(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
            on_chunk=on_chunk,
        )

    assert output["translated_text"] == "Hi there"
    assert received == ["Hi", "Hi there"]
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_translation_streaming.py -v`
Expected: FAIL — `_main_translation` 仍用 `chat`（非流式），`on_chunk` 参数不存在，`received` 为空 / TypeError: unexpected keyword `on_chunk`。

- [ ] **Step 3: 实现 `_main_translation` 流式 + `translate` 透传**

修改 `backend/app/services/translation.py`。

**(a)** 顶部 import 区，在 `import uuid` 之后新增一行：

```python
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
```

**(b)** `_main_translation` 增加 `on_chunk` 参数，调用点改为流式累积。最终方法为：

```python
    async def _main_translation(
        self,
        source_text: str,
        genre: str,
        strategy: str,
        target_language: str,
        cultural_constraints: CulturalPreprocessResult | None = None,
        cultural_sphere: str | None = None,
        audience_type: str | None = None,
        glossary_block: str = "",
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        system_prompt = build_translation_system_prompt(
            target_language=target_language,
            genre=genre,
            strategy=strategy,
            cultural_constraints=cultural_constraints,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
        )
        if glossary_block:
            system_prompt += f"\n\n{glossary_block}\n"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_text},
        ]
        # 流式累积：qwen-max 边生成边回调部分译文
        accumulated = ""
        async for chunk in bailian_client.chat_stream(model="qwen-max", messages=messages):
            accumulated += chunk
            if on_chunk:
                await on_chunk(accumulated)
        return accumulated
```

**(c)** `translate` 方法签名增加 `on_chunk` 参数（在 `cultural_constraints` 之后），并把 `_main_translation` 调用加上 `on_chunk=on_chunk`。`translate` 签名变为：

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
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict:
```

`_main_translation` 调用变为（在 `glossary_block=glossary_block,` 之后加一行）：

```python
        translated_text = await self._main_translation(
            source_text=source_text,
            genre=genre,
            strategy=strategy,
            target_language=target_language,
            cultural_constraints=cultural_result,
            cultural_sphere=cultural_sphere,
            audience_type=audience_type,
            glossary_block=glossary_block,
            on_chunk=on_chunk,
        )
```

**(d)** 删除 `translate_stream` 方法（含其 docstring，约文件末尾 `async def translate_stream(...)` 到 `yield chunk` 整段）。其 import（`STRATEGY_DESCRIPTIONS`/`TRANSLATION_SYSTEM_PROMPT`/`language_descriptor`）仍被 `build_translation_system_prompt`/`_risk_annotation` 使用，保留不动。

- [ ] **Step 4: 修改 `chat_stream` 超时 180s**

修改 `backend/app/llm/bailian.py` 的 `chat_stream`：将 `async with httpx.AsyncClient(timeout=120.0) as client:` 改为：

```python
        async with httpx.AsyncClient(timeout=180.0) as client:
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_translation_streaming.py -v`
Expected: PASS（4 个用例）。

再跑既有相关测试确认无回归：
Run: `cd backend && pytest tests/test_decision_extraction.py tests/test_translation_glossary.py tests/test_translation_prompt.py -v`
Expected: PASS（`test_decision_extraction` 用 `patch.object(pipeline, "_main_translation", ...)` 绕过流式；`on_chunk` 默认 None，向后兼容）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/translation.py backend/app/llm/bailian.py backend/tests/test_translation_streaming.py
git commit -m "feat(backend): stream translate stage with on_chunk partial-text callback"
```

---

### Task 2: Celery 任务 `make_chunk_writer` 节流落库 + 失败丢弃部分译文

**Files:**
- Modify: `backend/app/tasks.py`
- Test: `backend/tests/test_tasks_streaming.py`（创建）

**Interfaces:**
- Consumes: Task 1 的 `pipeline.translate(..., on_chunk=Callable[[str], Awaitable[None]])`；`TranslationResult` ORM 对象 `tr`（有 `translated_text` 属性）；`db`（async session，有 `commit()`）。
- Produces: `make_chunk_writer(tr, db, interval=STREAM_WRITE_INTERVAL) -> Callable[[str], Awaitable[None]]`——节流闭包，供 `translate(on_chunk=...)` 使用。

- [ ] **Step 1: 编写失败测试**

创建 `backend/tests/test_tasks_streaming.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_tasks_streaming.py -v`
Expected: FAIL — `ImportError: cannot import name 'make_chunk_writer' from 'app.tasks'`。

- [ ] **Step 3: 实现 `make_chunk_writer` + 接线 + 失败丢弃**

修改 `backend/app/tasks.py`。

**(a)** 顶部 import 区加 `import time`（在 `import asyncio` 之后）：

```python
import asyncio
import logging
import time
import uuid
```

**(b)** 模块级常量（在 `logger = logging.getLogger(__name__)` 之后）：

```python
# 流式部分译文落库节流间隔（秒）；前端 2s 轮询，每周期约 1-2 次更新
STREAM_WRITE_INTERVAL = 1.0


def make_chunk_writer(tr, db, interval: float = STREAM_WRITE_INTERVAL):
    """构造节流回调：每 interval 秒把部分译文写库，状态保持 streaming。

    首个 chunk 立即写（last 初值 0.0，now-0 恒 >= interval）。
    """
    last = {"t": 0.0}

    async def on_chunk(accumulated: str):
        now = time.monotonic()
        if now - last["t"] >= interval:
            tr.translated_text = accumulated
            await db.commit()
            last["t"] = now

    return on_chunk
```

**(c)** `_run_translation` 中 `pipeline.translate(...)` 调用前构造 `on_chunk` 并传入。将原：

```python
                    output = await pipeline.translate(
                        source_text=job.source_text,
                        genre=job.genre,
                        strategy=job.strategy,
                        target_language=lang,
                        cultural_sphere=job.cultural_sphere,
                        audience_type=job.audience_type,
                        cultural_constraints=cultural_constraints,
                        db=db,
                        user_id=job.user_id,
                    )
```

改为：

```python
                    on_chunk = make_chunk_writer(tr, db)
                    output = await pipeline.translate(
                        source_text=job.source_text,
                        genre=job.genre,
                        strategy=job.strategy,
                        target_language=lang,
                        cultural_sphere=job.cultural_sphere,
                        audience_type=job.audience_type,
                        cultural_constraints=cultural_constraints,
                        db=db,
                        user_id=job.user_id,
                        on_chunk=on_chunk,
                    )
```

**(d)** 失败路径丢弃部分译文。`_run_translation` 的 `except Exception` 块中，将：

```python
                    if tr:
                        tr.status = "failed"
                        await db.commit()
```

改为（在 `tr.status = "failed"` 之前加 `tr.translated_text = None`）：

```python
                    if tr:
                        tr.translated_text = None
                        tr.status = "failed"
                        await db.commit()
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_tasks_streaming.py -v`
Expected: PASS（2 个用例）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/tasks.py backend/tests/test_tasks_streaming.py
git commit -m "feat(backend): throttle-write partial translation in celery task"
```

---

### Task 3: 前端 streaming `▍` 光标

**Files:**
- Modify: `frontend/components/workspace/translation-result.tsx`
- Test: `frontend/components/workspace/__tests__/translation-result.test.tsx`（创建）

**Interfaces:**
- Consumes: `useTranslationStore.results[language]`（`status`、`translatedText`、`riskAnnotations` 等字段不变）；前端 2s 轮询已写 `translated_text`，本任务只改渲染。
- Produces: streaming + 有文本时在译文末尾渲染 `<span className="animate-pulse">▍</span>`；completed 不渲染。

- [ ] **Step 1: 编写失败测试**

创建 `frontend/components/workspace/__tests__/translation-result.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const translationState = vi.hoisted(() => ({
  results: {} as Record<string, any>,
  setResult: vi.fn(),
}));

vi.mock("@/stores/translation-store", () => ({
  useTranslationStore: vi.fn((selector?: (s: any) => any) =>
    selector ? selector(translationState) : translationState,
  ),
}));

vi.mock("../cultural-adaptation-panel", () => ({
  CulturalAdaptationPanel: () => null,
}));
vi.mock("../risk-annotation-popover", () => ({
  RiskAnnotationPopover: ({ children }: any) => <>{children}</>,
}));

import { TranslationResult } from "../translation-result";

const baseResult = {
  riskAnnotations: [],
  acceptanceScore: -1,
  highlightedIndex: null,
  culturalAdaptation: null,
};

describe("TranslationResult streaming cursor", () => {
  it("shows blinking cursor while streaming with text", () => {
    translationState.results = {
      "en-GB": { ...baseResult, status: "streaming", translatedText: "Hello" },
    };
    render(<TranslationResult language="en-GB" />);
    expect(screen.getByText("▍")).toBeInTheDocument();
  });

  it("hides cursor when completed", () => {
    translationState.results = {
      "en-GB": { ...baseResult, status: "completed", translatedText: "Hello world" },
    };
    render(<TranslationResult language="en-GB" />);
    expect(screen.queryByText("▍")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && ./node_modules/.bin/vitest run components/workspace/__tests__/translation-result.test.tsx`
Expected: FAIL — streaming 时找不到 `▍`（`Unable to find an element with the text: ▍`）。

- [ ] **Step 3: 实现 streaming 光标**

修改 `frontend/components/workspace/translation-result.tsx` 的 `content` useMemo 中 `if spans.length === 0` 分支。将：

```tsx
    if (spans.length === 0) {
      return <span>{result.translatedText}</span>;
    }
```

改为：

```tsx
    if (spans.length === 0) {
      if (result.status === "streaming") {
        return (
          <span>
            {result.translatedText}
            <span className="animate-pulse">▍</span>
          </span>
        );
      }
      return <span>{result.translatedText}</span>;
    }
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd frontend && ./node_modules/.bin/vitest run components/workspace/__tests__/translation-result.test.tsx`
Expected: PASS（2 个用例）。

- [ ] **Step 5: 提交**

```bash
git add frontend/components/workspace/translation-result.tsx frontend/components/workspace/__tests__/translation-result.test.tsx
git commit -m "feat(frontend): add streaming cursor to translation result"
```

---

### Task 4: 全量校验

**Files:** 无（仅运行校验）

- [ ] **Step 1: 后端测试（新 + 相关，不依赖 DB）**

Run: `cd backend && pytest tests/test_translation_streaming.py tests/test_tasks_streaming.py tests/test_decision_extraction.py tests/test_translation_glossary.py tests/test_translation_prompt.py -v`
Expected: 全部 PASS。

- [ ] **Step 2: 前端类型检查**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit`
Expected: 无错误。

- [ ] **Step 3: 前端测试**

Run: `cd frontend && ./node_modules/.bin/vitest run components/workspace/__tests__/translation-result.test.tsx`
Expected: PASS。

- [ ] **Step 4: 核对改动范围**

Run: `git diff <BASE>..HEAD --stat`（BASE 为本计划开始 commit）
Expected: 仅包含 `translation.py`、`bailian.py`、`tasks.py`、`translation-result.tsx` 及三个新测试文件的合理变更；无对 `chat`/`_risk_annotation`/`cultural_preprocess`/`retrieve_glossary_terms`/WS/轮询逻辑的改动。

---

## Self-Review

**1. Spec 覆盖：**
- `_main_translation` 流式 + on_chunk → Task 1 Step 3(b)。
- 流式路径注入 glossary + cultural_constraints（质量对齐）→ Task 1 Step 3(b) 复用 `build_translation_system_prompt` + `glossary_block`（不变）；测试 Step 1 `test_main_translation_injects_glossary_block_into_stream_prompt` 断言 glossary 注入。
- `translate` 透传 on_chunk → Task 1 Step 3(c)；测试 `test_translate_passes_on_chunk_to_main_translation`。
- 删除 `translate_stream` → Task 1 Step 3(d)。
- `chat_stream` 超时 180s → Task 1 Step 4。
- Celery 节流落库（`STREAM_WRITE_INTERVAL=1.0s`，首 chunk 立即写）→ Task 2 Step 3(b) `make_chunk_writer`；测试覆盖节流 + 首写。
- 失败丢弃部分译文（`translated_text=None`）+ failed + 退款 → Task 2 Step 3(d)（`tr.translated_text=None` 加入既有 except；退款为既有逻辑）；错误传播由 Task 1 `test_main_translation_propagates_stream_error` 覆盖。
- 前端 `▍` 光标（animate-pulse，streaming + 有文本）→ Task 3；测试覆盖显示/隐藏。
- 非目标（多语言并发、Level 3、max_tokens、risk 流式、WS、轮询间隔）→ 未触及，Global Constraints 已声明。

**2. 占位符扫描：** 无 TBD/TODO；每个代码步骤含完整代码；无"类似 Task N"。

**3. 类型一致性：** `on_chunk: Callable[[str], Awaitable[None]] | None` 在 `_main_translation`、`translate`、`make_chunk_writer` 返回的闭包三处签名一致；`make_chunk_writer(tr, db, interval=STREAM_WRITE_INTERVAL)` 在定义与调用一致；`STREAM_WRITE_INTERVAL` 在 Task 2 定义且仅在 `make_chunk_writer` 默认值引用。
