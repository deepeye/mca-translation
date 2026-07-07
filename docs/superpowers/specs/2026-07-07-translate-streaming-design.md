# translate 阶段流式输出设计（Level 1）

## 背景

点击「开始转译」后，翻译管线在 Celery 任务里串行跑各目标语言：`preprocess`（qwen-plus，1×）→ 每语言 `glossary`（DB+embed）→ `translate`（qwen-max，非流式 `chat`）→ `risk`（qwen-plus）。其中 `translate` 用 `bailian_client.chat(model="qwen-max")` 阻塞到完整返回，用户在结果区只能看到转圈，直到该语言全部译完才出文本——体感慢。

诊断结论：`translate` × 语言数是绝对主瓶颈，且多语言串行放大。流式输出**不降低总耗时**（qwen-max 该生成的 token 不变），但显著缩短首字时间、让译文逐步出现，改善感知延迟。

关键现成条件：
- `bailian_client.chat_stream` 已存在（async generator，yield content delta，支持 qwen-max）。
- 前端 `TranslationResult` 在 `status==="streaming"` 且有 `translatedText` 时**已渲染部分译文**；前端 2s 轮询每次用 DB 最新 `translated_text` 覆盖展示。
- 故只要后端在流式过程中把部分译文落库 + 状态保持 `streaming`，前端零功能改动即可逐步出字。

本设计为流式可行性评估中的 **Level 1**：后端流式 + 部分译文落库 + 复用 2s 轮询。

## 目标

- `translate` 阶段改用 `chat_stream` 流式输出，译文逐步出现而非全程转圈。
- 流式路径仍注入 glossary + cultural_constraints，与非流式质量一致。
- 流式过程中每 ~1s 把部分译文落库，前端 2s 轮询拉到逐步增长的文本。
- 流式出错时丢弃部分译文、标记 failed、退款，与现有失败语义一致。
- 前端复用现有渲染逻辑，仅加一个 streaming 光标润色。

## 非目标

- 不做多语言并发（`for lang` 仍串行，独立改动）。
- 不做 Level 3 Redis pub/sub 实时推送（仍用 2s 轮询）。
- 不设 `max_tokens` 上限（会截断译文）。
- 不改 `risk` 阶段（依赖完整译文，仍非流式，在 translate 完成后跑）。
- 不动 WebSocket、不缩短前端轮询间隔。
- 不加非流式回退重试（流式出错直接失败）。

## 方案选型

选用 **A. `on_chunk` 异步回调**：

- `_main_translation` 把 `chat` 换成 `chat_stream`，累积 chunk，每个 chunk 调 `on_chunk(accumulated)`。
- `translate(..., on_chunk=None)` 透传给 `_main_translation`。
- Celery 任务传一个节流闭包：每 ~1s 写 `tr.translated_text = accumulated` + commit，状态保持 `streaming`。
- `translate()` 仍返回最终 dict，risk 阶段在 `_main_translation` 返回后照跑，不动。

相比 B（`_main_translation` 变 async generator、任务消费、risk 提到任务层）与 C（任务内联流式、绕开 `translate()` 重写编排），A 契约改动最小、管线编排与 risk 阶段零改动、DB 持久化/节流归任务层管。

## 架构与组件变更

### 1. `backend/app/services/translation.py`

**`_main_translation`** 增加 `on_chunk` 参数，调用点由 `chat` 改为 `chat_stream` + 累积：

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
    system_prompt = build_translation_system_prompt(...)  # 不变
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

`chat` 默认 temperature 0.3，`chat_stream` 默认 0.3，行为一致。system_prompt + glossary_block 构建完全不变（质量对齐）。

**`translate`** 增加 `on_chunk=None`，透传：

```python
async def translate(
    self,
    ...,
    cultural_constraints: object = _CULTURAL_CONSTRAINTS_NOT_PROVIDED,
    on_chunk: Callable[[str], Awaitable[None]] | None = None,
) -> dict:
    ...
    translated_text = await self._main_translation(
        ...,
        on_chunk=on_chunk,
    )
    ...
```

risk 阶段（`_risk_annotation`）与 decision_entries 收集不变。

**删除** `translate_stream` 方法（约 line 330-345）：废弃存根，无调用方，被流式 `_main_translation` 取代。同时移除其专属 import（如 `STRATEGY_DESCRIPTIONS`、`TRANSLATION_SYSTEM_PROMPT`、`language_descriptor` 中仅被它使用的部分需确认是否仍被他处引用，若否一并移除）。

### 2. `backend/app/llm/bailian.py`

`chat_stream` 的 `httpx.AsyncClient(timeout=...)` 由 120s 改为 **180s**，与 `chat` 一致，避免长文流式断流。不设 `max_tokens`。

### 3. `backend/app/tasks.py` `_run_translation`

模块级常量：

```python
STREAM_WRITE_INTERVAL = 1.0  # 流式部分译文落库节流间隔（秒）
```

在 `pipeline.translate(...)` 调用前定义节流闭包并传入：

```python
import time
...
last_write = 0.0
async def on_chunk(accumulated: str):
    nonlocal last_write
    now = time.monotonic()
    if now - last_write >= STREAM_WRITE_INTERVAL:
        tr.translated_text = accumulated
        await db.commit()
        last_write = now

output = await pipeline.translate(
    source_text=job.source_text,
    ...,
    on_chunk=on_chunk,
)
```

- `tr.status` 在 translate 前已是 `"streaming"`（现 line 82/87），`on_chunk` 只更新 `translated_text`。
- 首个 chunk 立即写（`last_write=0.0`，`now - 0 >= 1.0` 恒真），用户尽早在下一次 2s 轮询看到首段。
- translate 返回后照旧设最终 `tr.translated_text = output["translated_text"]`（追上最后一段）+ `risk_annotations` + `status=completed`。
- `time` 模块在文件顶部 import。

**失败路径**（`except Exception` 块，现 line 143）：增加 `tr.translated_text = None`（丢弃部分译文），再设 `status=failed` + 退款，与"直接失败"语义一致。与既有 `INSUFFICIENT` 失败路径（line 136 `tr.translated_text = None`）对齐。

### 4. `frontend/components/workspace/translation-result.tsx`

无功能改动（`streaming` + 有 text 时已渲染 `content`）。增加 streaming 光标润色：当 `result.status === "streaming"` 且 `result.translatedText` 非空时，在渲染文本末尾追加一个 `▍` 闪烁光标（CSS 劥画），提示正在生成。

实现：在 `content` useMemo 内，`streaming` 且有文本时，于现有 `<span>{result.translatedText}</span>`（无 risk spans 分支）末尾追加 `<span className="streaming-cursor">▍</span>`；有 risk spans 分支同理在末尾 parts 追加。`streaming-cursor` 用 Tailwind animate-pulse 或自定义 blink 动画。

### 5. 其它

- 前端轮询（`input-panel.tsx pollJobStatus`）：无改动，已每次读 `translated_text`。
- WebSocket、`chat`、`_risk_annotation`、`cultural_preprocess`、`retrieve_glossary_terms`：无改动。

## 数据流

1. 点击「开始转译」→ `POST /api/jobs` → Celery `run_translation`。
2. `preprocess`（1×，qwen-plus，不变）。
3. 逐语言（串行，不变）：`tr.status="streaming"` → `pipeline.translate(on_chunk)`：
   - `glossary`（DB+embed，不变）。
   - `_main_translation` 流式 qwen-max，累积 chunk，`on_chunk` 每 ~1s 写 `tr.translated_text` + commit。
   - 前端 2s 轮询拉到逐步增长的 `translated_text` → `TranslationResult` 渲染 + `▍` 光标。
   - translate 完成 → `_risk_annotation`（不变）→ 返回。
4. 任务设最终 `translated_text` + `risk_annotations` + `status=completed`，前端渲染 risk 标注、光标消失。
5. 流式出错 → 异常冒泡 → 任务 `except` → `tr.translated_text=None` + `status=failed` + 退款；前端显示失败文案（不显示部分译文）。

## 错误处理

- 流式过程中 `chat_stream` 抛错（网络 / 超时 / qwen 报错）→ 异常向上传播 → `_run_translation` 的 `except Exception` 捕获 → `tr.translated_text=None`、`tr.status=failed`、退款。无回退、无重试。
- `chat_stream` 超时 180s 与 `chat` 一致；长文若超 180s 仍会断流失败（按上述失败语义处理）。
- on_chunk 内 `db.commit()` 失败属异常，向上传播并走同一失败路径。
- risk 阶段失败语义不变（`_risk_annotation` 内部 try/except 返回 `[]`）。

## UI 文案

| 元素 | 文案 / 表现 |
|---|---|
| streaming 且无文本 | 正在生成...（现有，不变） |
| streaming 且有文本 | 逐步增长的译文 + 末尾 `▍` 闪烁光标 |
| completed | 完整译文 + risk 标注（现有，不变） |
| failed | 失败提示（现有，不变） |

## 测试计划（后端 pytest）

- **`tests/services/test_translation.py`**（新增/扩展）：
  - mock `bailian_client.chat_stream` 依次 yield `["Hello", " world"]`；调 `_main_translation(on_chunk=mock_cb)`；断言 `mock_cb` 依次收到 `"Hello"`、`"Hello world"`，返回 `"Hello world"`。
  - 断言流式路径 system_prompt 仍含 glossary_block 与 cultural_constraints（质量对齐）——可通过 spy `build_translation_system_prompt` 或检查传入 `chat_stream` 的 messages。
  - `translate(on_chunk=...)` 透传：on_chunk 在 risk 之前被调用；risk 仍正常返回。
- **`tests/tasks/test_run_translation.py`**（新增/扩展）：
  - on_chunk 节流：连续两次回调间隔 <1s 时只 commit 一次（验证 `last_write` 节流）。
  - translate 返回后最终 `translated_text` 落库、`status=completed`。
  - 流式抛错 → `tr.translated_text=None` + `status=failed` + 触发退款。
- **`tests/llm/test_bailian.py`**（若存在，否则新增）：`chat_stream` 客户端超时为 180s。
- 前端：`translation-result.test.tsx` 增加 streaming + 有文本时渲染 `▍` 光标的断言。

## 验收标准

- [ ] 点击「开始转译」后，译文在 ~2-3s 内开始出现在结果区并逐步增长，而非全程转圈直到完成。
- [ ] 流式路径仍注入 glossary + cultural_constraints，与非流式质量一致。
- [ ] 流式完成后 risk 标注出现，状态 `completed`，`▍` 光标消失。
- [ ] 流式出错 → 该语言 failed、部分译文丢弃（`translated_text=None`）、信用分退还。
- [ ] `translate_stream` 存根已删除，无遗留引用。
- [ ] `chat_stream` 超时为 180s。
- [ ] 多语言仍串行（本范围不改），每种语言依次流式。
- [ ] 后端测试通过；前端 streaming 光标测试通过。
