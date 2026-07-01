# 高语境术语内联高亮 — 输入区自动识别与悬停转译建议

**日期**: 2026-07-01
**状态**: 设计已确认

## 1. 概述

### 1.1 背景

当前输入区 `TextEditor` 已集成 `TermHighlighter`，但该组件**只把术语库命中的词条以 badge 列表形式贴在 textarea 下方**，并未在原文上做内联高亮；且其数据源仅来自 `/api/glossary/detect`（用户/系统术语库子串匹配 + 硬编码回退），**不识别超出术语库字面匹配的文化隐喻/政治话语**。

与此同时，后端 `cultural_preprocess`（`backend/app/services/cultural.py`）已具备 LLM 驱动的文化负载词识别能力，产出 `CulturalLoadedTerm`（含 `term / culture_gap / adaptation_strategy / suggested_rendering / reason`），但该能力**只在翻译管线内运行**，输入阶段无法触达。

### 1.2 目标

- 在输入区 textarea 上做**内联高亮**（非下方 badge 列表），覆盖两类高语境术语：
  - 术语库命中（政治话语/文化隐喻等字面匹配，实时）
  - LLM 识别的文化负载词（隐喻/政治话语语义识别，手动触发）
- 悬停高亮片段显示 Popover，展示术语分类、风险备注、转译建议（`suggested_rendering`）与适配理由
- 输入区新增「分析高语境词」按钮，手动触发 LLM 隐喻识别（绑定目标文化圈 + 受众类型）
- 识别结果接入决策日志（新增 `cultural_term_detection` 阶段）

### 1.3 非目标

- 不改写 `CULTURAL_PREPROCESS_PROMPT` —— 该 prompt 同时供翻译管线使用，改写可能影响翻译质量
- 不做实时 LLM 隐喻识别 —— 每次输入都调 qwen-plus 成本/延迟过高，改为手动触发
- 不在本期打通「文化负载词 → 译后风险标注种子」链路 —— 留作 Phase 2，避免与现有 risk_annotation 双轨
- 不替换 `TermHighlighter` —— 保留为 badge 列表（术语库概览），内联高亮为新增独立组件

## 2. 设计决策

### 2.1 内联高亮实现：textarea + overlay 镜像层

| 方案 | 决策 |
|---|---|
| A：textarea + 透明镜像 div overlay | 💡 选定 — 保留原生 textarea 输入/IME 体验，镜像层同步文本与高亮 `<mark>` |
| B：contentEditable div | ❌ 舍弃 — 光标/输入/IME 控制复杂，与受控 React 状态难协调 |
| C：仅扩展 badge 列表 | ❌ 舍弃 — 不满足"内联高亮"需求 |

**镜像层技巧**：textarea 文本颜色透明（`color: transparent`）但光标保留（`caret-color: currentColor`）；其下方绝对定位一个同字体度量、同 padding、同 `white-space: pre-wrap` 的镜像 div，渲染原文 + `<mark>` 区间。textarea 滚动时同步镜像 `scrollTop`。

### 2.2 隐喻识别触发：手动按钮

| 方案 | 决策 |
|---|---|
| A：手动「分析高语境词」按钮 | 💡 选定 — 省 LLM 成本；`cultural_preprocess` 需目标文化圈参数，用户未选时禁用按钮 |
| B：debounce 自动触发 | ❌ 舍弃 — 每次输入烧一次 qwen-plus，且文化圈未定时无法跑 |
| C：仅译时附带 | ❌ 舍弃 — 输入阶段无高亮，体验回退 |

按钮状态机：`idle → loading → analyzed`；文本变更后置 `stale`（提示用户重新分析），不自动重跑。

### 2.3 offset 计算

`cultural_preprocess` 返回的 `CulturalLoadedTerm` 仅含 `term` 字符串，**无文本偏移**。采用服务端计算：在 `/api/glossary/detect-cultural` 端点内，对每个 `term` 在 `source_text` 中查找全部出现位置（`str.find` 循环），返回 `{term, offset, length, ...}`。多次出现全部高亮。

术语库命中词（来自既有 `/api/glossary/detect`）无 offset，由**前端**按 `source_term` 子串搜索计算 offset，统一为 `HighlightSpan[]`。

### 2.4 决策日志阶段

`decision_log.stage` 为 `String(16)` 字符串列（无 CHECK 约束，但有长度限制）。新增 `cultural_detect` 阶段值（15 字符，fits 16）到 `_STAGE_ORDER`，**纯代码改动，无需 Alembic 迁移**。该阶段记录输入区 LLM 识别出的文化负载词决策，与翻译时 `preprocess` 阶段（`culture_term_adaptation`）区分：前者是输入期独立识别，后者是翻译管线内的约束注入。

> 注：阶段名取 `cultural_detect` 而非 `cultural_term_detection`，因后者 23 字符超过 `String(16)` 长度限制（PG VARCHAR 会报错而非截断）。

## 3. 后端设计

### 3.1 新增端点 `POST /api/glossary/detect-cultural`

```
POST /api/glossary/detect-cultural
Body: { text, cultural_sphere, audience_type, genre }
Resp: {
  terms: [
    {
      term, offset, length,
      culture_gap: "low"|"medium"|"high",
      adaptation_strategy: "literal"|"explanatory"|"analogical"|"reconstruction",
      suggested_rendering, reason,
      term_type: "cultural_metaphor"  // 固定，供前端分类着色
    }
  ],
  stale: false  // 占位，预留
}
```

实现要点：
- 复用 `cultural_preprocess()`，不新建 prompt 模板
- `cultural_sphere` 不在 `CULTURAL_SPHERE_PROFILES` 或 `audience_type` 不在 `AUDIENCE_TYPE_GUIDELINES` 时返回空 `terms`（不报错，降级）
- LLM 调用失败 / JSON 解析失败 → 返回空 `terms`（`cultural_preprocess` 已返回 None）
- offset 计算：对每个 `term` 在 `text` 中 `find` 全部出现，去重；`term` 为空或未找到则跳过该词（不计入）

### 3.2 决策日志阶段扩展

`backend/app/services/decision_log.py` 的 `_STAGE_ORDER` 新增：

```python
_STAGE_ORDER = {
    "preprocess": 0,
    "cultural_detect": 0,   # 输入期识别，与 preprocess 同序（可并列展示）
    "glossary": 1,
    "translate": 2,
    "risk": 3,
    "suggestion": 4,
}
```

`backend/app/models/decision_log.py` `stage` 列注释补充 `cultural_detect`。前端 `DecisionLogEntry` 的 `stage` 联合类型补充该值。

> 本期不在 `/api/glossary/detect-cultural` 内写决策日志（该端点无 job_id/result_id 上下文）。决策日志的 `cultural_detect` 阶段条目由翻译管线在 `tasks.py` 中从输入期识别结果（若用户已分析）注入——Phase 2 落地；本期仅打通类型与排序。

## 4. 前端设计

### 4.1 新增 `InlineHighlighter` 组件

`frontend/components/workspace/inline-highlighter.tsx`

职责：渲染 textarea + 镜像 overlay，消费统一的 `HighlightSpan[]`，每段 `<mark>` 悬停显示原生 absolute Popover。

```ts
interface HighlightSpan {
  start: number;      // 原文偏移
  end: number;
  text: string;       // 原文片段
  source: "glossary" | "cultural";
  term_type: string;  // 分类，用于着色
  // Popover 内容
  label: string;      // 分类中文名
  risk_notes?: string;
  suggestion?: string;      // suggested_rendering
  reason?: string;
  culture_gap?: "low"|"medium"|"high";
}
```

镜像层将原文按 `HighlightSpan`（按 start 排序、合并重叠时 glossary 优先）切片，非高亮段为纯文本，高亮段为 `<mark class="...">`。`<mark>` 为 `position: relative`，hover 时 `absolute bottom-full` 弹出 Popover（复用现有 `TermHighlighter` 的原生 div 模式）。

颜色：`source=glossary` 沿用 `TERM_TYPE_BADGE_CLASS`；`source=cultural` 用赤陶系（`bg-orange-100/60` 底 + `border-b-2 border-orange-400`），与品牌赤陶呼应。

### 4.2 `TextEditor` 改造

- 用 `InlineHighlighter` 替换 `<textarea>` + 下方 `TermHighlighter` 的组合（`TermHighlighter` badge 列表保留在 inline 之下作为概览，或移除——本期保留为概览，避免功能回退）
- 新增「🔍 分析高语境词」按钮，置于 textarea 工具条；点击调 `apiClient.detectCulturalTerms(text, culturalSphere, audienceType, genre)`
- 按钮状态：未选文化圈时 disabled + tooltip 提示；loading 时 spinner；analyzed 后显示"已分析 N 个高语境词"；文本变更后置 stale

### 4.3 store 扩展

`glossary-store.ts` 新增：
```ts
culturalTerms: CulturalTerm[];      // LLM 识别结果（带 offset）
culturalAnalysisState: "idle"|"loading"|"analyzed"|"stale";
analyzeCulturalTerms: (text, sphere, audience, genre) => Promise<void>;
```
`detect`（术语库）逻辑保留。文本变更时若 `culturalAnalysisState === "analyzed"` 则置 `stale`。

### 4.4 api-client 扩展

```ts
async detectCulturalTerms(body: {
  text: string; cultural_sphere: string; audience_type: string; genre: string;
}): Promise<{ terms: CulturalTermResult[] }>
```

## 5. 边界与风险

- **IME 组合态**：输入法组合期间不重算高亮区间，监听 `compositionstart/compositionend`，`compositionend` 后再触发 detect debounce
- **字体度量**：textarea 与镜像 div 必须 1:1（font-family/size/line-height/padding/letter-spacing/word-break/white-space）；抽公共 `textarea-mirror.css` 类避免漂移
- **重叠区间**：同一片段被术语库与文化词同时命中——glossary 优先，cultural 被吸收不重复高亮（Popover 内可并列显示两条建议，本期简化为 glossary 优先）
- **大文本**：文本 > 5000 字时禁用 LLM 分析按钮（成本保护），提示"原文过长，建议分段"
- **LLM 失败**：按钮回退 idle，toast 提示"识别失败，请重试"，不阻塞输入与术语库实时高亮

## 6. 测试

- 后端：`tests/test_glossary_detect_cultural.py` —— mock `bailian_client.chat`，验证 offset 计算、多次出现、未知文化圈降级、LLM 失败降级
- 前端：`inline-highlighter.test.tsx` —— 区间切片渲染、hover Popover 内容、IME 期间不重算
- 决策日志：`test_decision_log_stage_order` —— `cultural_term_detection` 排序正确
