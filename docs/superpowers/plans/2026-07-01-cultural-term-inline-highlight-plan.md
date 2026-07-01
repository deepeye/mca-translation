# 高语境术语内联高亮 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在输入区 textarea 上实现高语境术语内联高亮——整合术语库命中（实时）与 LLM 文化负载词识别（手动触发），悬停显示转译建议；后端新增 `/api/glossary/detect-cultural` 端点复用 `cultural_preprocess`；决策日志新增 `cultural_detect` 阶段。

**Architecture:** 后端在 `app/api/glossary.py` 新增 `POST /detect-cultural`，内部调用 `cultural_preprocess()` 并服务端计算每个 `term` 的全部 offset，返回带区间的结构化结果。`decision_log.py` 的 `_STAGE_ORDER` 新增 `cultural_detect`（纯代码，无迁移）。前端新增 `InlineHighlighter`（textarea + 透明镜像 div overlay），消费统一 `HighlightSpan[]`；`TextEditor` 集成该组件 + 「分析高语境词」按钮；`glossary-store` 扩展 `culturalTerms` 与分析状态机；`api-client` 新增 `detectCulturalTerms`。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Pydantic v2（后端）；Next.js App Router + Zustand + Tailwind + shadcn/ui（前端，栈为 Base UI 非 Radix）。

## Global Constraints

- 不改 `CULTURAL_PREPROCESS_PROMPT`（同时供翻译管线，避免影响翻译质量）
- 不做实时 LLM 隐喻识别（手动按钮触发，省成本）
- 不打通「文化词 → 译后风险种子」（Phase 2）
- `decision_log.stage` 为 `String(16)` 字符串列无 CHECK 约束但有长度限制，新增阶段值 `cultural_detect`（15 字符，fits 16）无需 Alembic 迁移
- 前端栈为 Base UI（`@base-ui/react`）非 Radix；hover Popover 用原生 absolute div（与现有 `TermHighlighter` 一致）
- 前端写代码前读 `frontend/node_modules/next/dist/docs/` 相关指南（AGENTS.md 强制）
- 品牌色系：青绿（术语库）+ 赤陶（文化隐喻 LLM 识别）
- 代码注释中英双语，重要逻辑中文注释
- 后端测试 `pytest -v`（需 `docker compose -f docker-compose.dev.yml up -d` 起 pg/redis）
- 前端测试 `pnpm test`
- Alembic head：`17e8dc671db3`（本期无新迁移）

---

### Task 1: 后端 — `/api/glossary/detect-cultural` 端点

**Files:**
- Modify: `backend/app/api/glossary.py`
- Modify: `backend/app/schemas/glossary.py`（若存在；否则在 glossary.py 内定义 Pydantic 模型，与现有 `_DetectRequest` 风格一致）

**Interfaces:**
- Consumes: `app.services.cultural.cultural_preprocess`, `app.llm.bailian.bailian_client`, `app.schemas.job.CulturalPreprocessResult`
- Produces: `POST /api/glossary/detect-cultural` 端点

- [x] **Step 1: 定义请求/响应 Pydantic 模型**

在 `glossary.py` 顶部模型区新增（与 `_DetectRequest` 同风格，中英双语注释）：

```python
class _CulturalDetectRequest(BaseModel):
    text: str
    cultural_sphere: str
    audience_type: str
    genre: str


class _CulturalDetectedTerm(BaseModel):
    term: str
    offset: int
    length: int
    culture_gap: str  # low|medium|high
    adaptation_strategy: str
    suggested_rendering: str
    reason: str
    term_type: str = "cultural_metaphor"  # 固定分类，供前端着色


class _CulturalDetectResponse(BaseModel):
    terms: list[_CulturalDetectedTerm]
```

- [x] **Step 2: 实现 offset 计算辅助函数**

```python
def _find_all_occurrences(haystack: str, needle: str) -> list[int]:
    """返回 needle 在 haystack 中所有出现位置的首字符偏移。空串或未命中返回 []。"""
    if not needle:
        return []
    offsets: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            break
        offsets.append(idx)
        start = idx + len(needle)  # 允许重叠跳过；多次出现全部计入
    return offsets
```

- [x] **Step 3: 实现端点**

```python
@router.post("/detect-cultural", response_model=_CulturalDetectResponse)
async def detect_cultural_terms(
    body: _CulturalDetectRequest,
    user: User = Depends(get_current_user),
):
    """识别源文本中的文化负载词（隐喻/政治话语），返回带文本偏移的转译建议。

    复用 cultural_preprocess；任何降级（未知文化圈/受众、LLM 失败、JSON 解析失败）
    都返回空 terms，不报错——输入期识别为附属能力，不阻塞用户。
    """
    if not body.text:
        return _CulturalDetectResponse(terms=[])

    result = await cultural_preprocess(
        text=body.text,
        cultural_sphere=body.cultural_sphere,
        audience_type=body.audience_type,
        genre=body.genre,
        llm_client=bailian_client,
    )
    if result is None:
        return _CulturalDetectResponse(terms=[])

    items: list[_CulturalDetectedTerm] = []
    for t in result.culture_loaded_terms:
        for offset in _find_all_occurrences(body.text, t.term):
            items.append(_CulturalDetectedTerm(
                term=t.term,
                offset=offset,
                length=len(t.term),
                culture_gap=t.culture_gap,
                adaptation_strategy=t.adaptation_strategy,
                suggested_rendering=t.suggested_rendering,
                reason=t.reason,
            ))
    return _CulturalDetectResponse(terms=items)
```

- [x] **Step 4: 导入 `cultural_preprocess` 与 `bailian_client`**

在 `glossary.py` import 区补：
```python
from app.llm.bailian import bailian_client
from app.services.cultural import cultural_preprocess
```

---

### Task 2: 后端 — 决策日志 `cultural_detect` 阶段

**Files:**
- Modify: `backend/app/services/decision_log.py`
- Modify: `backend/app/models/decision_log.py`（注释）

- [x] **Step 1: `_STAGE_ORDER` 新增阶段**

```python
_STAGE_ORDER = {
    "preprocess": 0,
    "cultural_detect": 0,  # 输入期识别，与 preprocess 同序
    "glossary": 1,
    "translate": 2,
    "risk": 3,
    "suggestion": 4,
}
```

- [x] **Step 2: 更新 `models/decision_log.py` `stage` 列注释**

将注释改为：`# 决策阶段：preprocess / cultural_detect / glossary / translate / risk / suggestion`

- [x] **Step 3: 前端类型同步（在 Task 4 一并处理）**

`frontend/lib/api-client.ts` 的 `DecisionLogEntry.stage` 联合类型补 `"cultural_detect"`。

---

### Task 3: 后端测试 — `test_glossary_detect_cultural.py`

**Files:**
- Create: `backend/tests/test_glossary_detect_cultural.py`

- [x] **Step 1: mock `bailian_client.chat` 返回结构化文化负载词**

用 `monkeypatch` 替换 `app.api.glossary.bailian_client` 的 `chat`，返回 `CulturalPreprocessResult` JSON。

- [x] **Step 2: 用例**

- [x] offset 正确：`term="人类命运共同体"` 在文本出现 2 次 → 返回 2 条，offset 正确
- [x] 未知 cultural_sphere → 返回空 terms（不报错）
- [x] LLM 调用抛异常 → 返回空 terms
- [x] JSON 解析失败（mock 返回非法 JSON）→ 返回空 terms
- [x] 空 text → 返回空 terms
- [x] term 在原文中不存在（LLM 幻觉）→ 该词不计入

---

### Task 4: 前端 — `api-client` 与 `glossary-store` 扩展

**Files:**
- Modify: `frontend/lib/api-client.ts`
- Modify: `frontend/stores/glossary-store.ts`
- Modify: `frontend/lib/glossary-categories.ts`（新增 cultural 配色常量）

- [x] **Step 1: `api-client` 新增类型与方法**

```ts
export interface CulturalTermResult {
  term: string;
  offset: number;
  length: number;
  culture_gap: "low" | "medium" | "high";
  adaptation_strategy: string;
  suggested_rendering: string;
  reason: string;
  term_type: string;
}

async detectCulturalTerms(body: {
  text: string;
  cultural_sphere: string;
  audience_type: string;
  genre: string;
}): Promise<{ terms: CulturalTermResult[] }> {
  return this.post("/api/glossary/detect-cultural", body);
}
```

同步更新 `DecisionLogEntry.stage` 联合类型补 `"cultural_detect"`。

- [x] **Step 2: `glossary-categories.ts` 新增 cultural 配色**

```ts
export const CULTURAL_HIGHLIGHT_CLASS =
  "bg-orange-100/60 border-b-2 border-orange-400";  // 赤陶系，与品牌呼应
export const CULTURAL_TERM_LABEL = "文化负载词（LLM 识别）";
```

- [x] **Step 3: `glossary-store` 扩展**

```ts
interface GlossaryState {
  // 既有...
  culturalTerms: CulturalTermResult[];
  culturalAnalysisState: "idle" | "loading" | "analyzed" | "stale";
  setCulturalTerms: (terms: CulturalTermResult[]) => void;
  setCulturalAnalysisState: (s: GlossaryState["culturalAnalysisState"]) => void;
}
```

文本变更时（在 `setText` 调用路径或 `TermHighlighter` effect 中）若 `culturalAnalysisState === "analyzed"` → 置 `stale`。

---

### Task 5: 前端 — `InlineHighlighter` 组件

**Files:**
- Create: `frontend/components/workspace/inline-highlighter.tsx`
- Create: `frontend/components/workspace/textarea-mirror.css`（公共字体度量类，必要时内联到组件 className）

**Interfaces:**
- Consumes: `useGlossaryStore`（detectedTerms + culturalTerms）, `useWorkspaceStore`（text + setText）
- Produces: `<InlineHighlighter />`，内部渲染 textarea + 镜像 div + hover Popover

- [x] **Step 1: 读 Next.js 文档（AGENTS.md 强制）**

浏览 `frontend/node_modules/next/dist/docs/` 中与 `"use client"` 组件、`useRef`、事件处理相关指南；记录任何 breaking change（如事件命名、ref 行为）。

- [x] **Step 2: 定义统一 `HighlightSpan` 与合并逻辑**

```ts
interface HighlightSpan {
  start: number; end: number; text: string;
  source: "glossary" | "cultural";
  term_type: string; label: string;
  risk_notes?: string; suggestion?: string;
  reason?: string; culture_gap?: "low"|"medium"|"high";
}
```

- glossary spans：从 `detectedTerms` 按 `source_term` 在 `text` 中 `indexOf` 全部出现，生成区间
- cultural spans：直接用 `culturalTerms` 的 `offset/length`
- 合并：按 start 排序；重叠区间 glossary 优先，cultural 被吸收

- [x] **Step 3: 镜像层切片渲染**

将 `text` 按 `HighlightSpan[]` 切片为段数组，非高亮段渲染纯文本，高亮段渲染 `<mark className={...} onMouseEnter/Leave>`。镜像 div 与 textarea 共享 `TEXTAREA_MIRROR_CLASS`（font/padding/line-height/white-space:pre-wrap/word-break 一致）。

- [x] **Step 4: textarea 透明文本 + 光标保留**

```tsx
<textarea
  value={text}
  onChange={(e) => setText(e.target.value)}
  className="... text-transparent caret-current ..."
/>
```

- [x] **Step 5: 滚动同步**

`onScroll` 同步镜像 div 的 `scrollTop/scrollLeft`。

- [x] **Step 6: IME 组合态守卫**

`compositionstart` → 置 `isComposing=true`；`compositionend` → 置 false 并触发 detect 重算。组合期间不重算高亮区间。

- [x] **Step 7: hover Popover（原生 absolute）**

每个 `<mark>` 为 `position: relative`；hover 时在 `absolute bottom-full left-0 z-50` 弹出内容：term、label、suggestion（赤陶色）、reason、risk_notes。复用现有 `TermHighlighter` 的 popover DOM 模式。

---

### Task 6: 前端 — `TextEditor` 集成与分析按钮

**Files:**
- Modify: `frontend/components/workspace/text-editor.tsx`

- [x] **Step 1: 用 `InlineHighlighter` 替换 textarea**

保留 `TermHighlighter` badge 列表在其下方作为术语概览（不回退现有功能）。

- [x] **Step 2: 「分析高语境词」按钮**

工具条按钮，从 `useWorkspaceStore` 取 `culturalSphere/audienceType/genre` 与 `input.text`：
- 未选文化圈 → disabled + tooltip "请先选择目标文化圈"
- text.length > 5000 → disabled + tooltip "原文过长，建议分段"
- 点击 → `analyzeCulturalTerms`；loading 显示 spinner；analyzed 显示"已分析 N 个高语境词"；stale 显示"原文已变更，建议重新分析"

- [x] **Step 3: 文本变更置 stale**

`setText` 后若 `culturalAnalysisState === "analyzed"` → `setCulturalAnalysisState("stale")`。

---

### Task 7: 前端测试

**Files:**
- Create: `frontend/components/workspace/__tests__/inline-highlighter.test.tsx`（路径按现有测试约定）

- [x] **Step 1: 用例**
- [x] 区间切片渲染：给定 `HighlightSpan[]`，`mark` 数量与区间数一致
- [x] 重叠合并：glossary 与 cultural 重叠时只渲染一个 mark（glossary 优先）
- [x] hover Popover 内容：suggestion/reason 正确显示
- [x] IME 守卫：~~`compositionstart` 期间不重算~~ — overlay 架构不修改 textarea，IME 组合天然不受干扰，无需守卫（设计调整）

---

### Task 8: 文档更新

**Files:**
- Modify: `CLAUDE.md`

- [x] **Step 1: 功能模块速览新增条目**

在「功能模块速览」增加「高语境术语内联高亮」小节，注明：输入区内联高亮、术语库实时 + LLM 手动识别、悬停转译建议、详情 `frontend/components/workspace/inline-highlighter.tsx` + `backend/app/api/glossary.py` `/detect-cultural`。

- [x] **Step 2: 决策日志阶段补 `cultural_detect`**

---

## 验收

- [x] `pytest -v` 全绿（含新增 `test_glossary_detect_cultural.py` 与 `test_decision_log_stage_order`）
- [x] `pnpm test` 全绿（含 `inline-highlighter.test.tsx`）
- [ ] 手动验证：输入含"人类命运共同体"等政治话语，术语库实时高亮；选文化圈后点「分析高语境词」，文化隐喻内联高亮，悬停显示建议
- [ ] IME 输入中文不卡顿、不错位
- [ ] LLM 失败时按钮回退、不阻塞输入
