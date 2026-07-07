# 输入区政治话语/文化隐喻手动触发识别设计

## 背景

当前输入区同时存在两层识别能力：

1. **术语库自动匹配**（`TermHighlighter`）：用户输入后 800ms debounce 自动调用 `/api/glossary/detect`，在输入区正文高亮命中词，并在下方以 badge 列表展示。
2. **LLM 文化负载词手动识别**（`TextEditor` 中“分析高语境词”按钮）：点击后调用 `/api/glossary/detect-cultural`，返回带偏移的文化负载词，由内联高亮渲染。

用户希望输入区对政治话语/文化隐喻的识别统一改为手动触发，避免输入过程中自动识别带来的干扰。

## 目标

- 输入区不再随用户输入自动识别政治话语/文化隐喻。
- 保留一个手动触发入口，统一执行术语库检测与 LLM 文化负载词检测。
- 识别结果仍以内联 mark 高亮展示，hover 行为保持现有设计。
- 不新增后端接口，复用现有 `/api/glossary/detect` 与 `/api/glossary/detect-cultural`。

## 非目标

- 不修改 `InlineHighlighter` 的渲染逻辑与 hover Popover 内容。
- 不调整后端 cultural_preprocess 或术语库检测逻辑。
- 不在输入区新增阻断式错误提示。

## 方案选型

选用 **A. 轻量改造**：

- 仅移除 `TermHighlighter` 的自动检测逻辑，保留组件与 hover tooltip。
- 复用现有“分析高语境词”按钮作为统一入口，点击时串行调用两个检测接口。
- 不改 `glossary-store` 结构，仅调整 `TextEditor` 调用顺序。

相比统一状态层或精简界面方案，此方案改动面最小，风险最低。

## 架构与组件变更

### 1. `frontend/components/workspace/text-editor.tsx`

- 移除 `TermHighlighter` 的 `useEffect` 自动检测（删除 800ms debounce 及 `detect` callback）。
- “分析高语境词”按钮改为统一入口：
  - 文案改为“分析术语与文化负载词”。
  - 点击时先调用 `apiClient.detectTerms(text)`，再调用 `apiClient.detectCulturalTerms(...)`。
  - 两个结果分别写入 `detectedTerms` 和 `culturalTerms`。
- 按钮状态机沿用 `idle → loading → analyzed → stale`：
  - `analyzed`：显示“已分析 N 个术语与文化负载词”（N 为 `detectedTerms.length + culturalTerms.length`）。
  - `stale`：文本变更后由现有逻辑触发，提示“原文已变更，重新分析”。
- 文本变更后不清空已有高亮，仅把按钮置为 stale，用户可重新分析。

### 2. `frontend/components/workspace/term-highlighter.tsx`

- 删除自动检测相关的 `useEffect`、`useRef`、`useCallback`。
- 组件变为纯展示组件：接收 `detectedTerms` 并渲染 badge 列表与 hover tooltip。
- 保留 `containerClassName` prop 与现有样式。

### 3. `frontend/components/workspace/inline-highlighter.tsx`

- 无改动。继续从 `useGlossaryStore` 读取 `detectedTerms` 与 `culturalTerms`，合并渲染 mark 与 hover Popover。

### 4. 后端

- 无改动。

## 数据流

1. 用户输入文本：不触发检测，`detectedTerms` / `culturalTerms` 保持当前值。
2. 用户点击“分析术语与文化负载词”：
   - `culturalAnalysisState` → `loading`。
   - 调用 `POST /api/glossary/detect` → 写入 `detectedTerms`。
   - 调用 `POST /api/glossary/detect-cultural` → 写入 `culturalTerms`。
   - `culturalAnalysisState` → `analyzed`。
3. 用户继续编辑文本：
   - 现有 `useEffect` 将 `analyzed` → `stale`。
   - 已有高亮保留，按钮提示重新分析。

## 错误处理

- 任一接口失败时独立降级，不影响另一部分结果：
  - `detectTerms` 失败 → `detectedTerms = []`。
  - `detectCulturalTerms` 失败 → `culturalTerms = []`。
- 两者都失败时按钮回到 `idle`；部分失败时回到 `analyzed` 并展示成功部分。
- 不弹出阻断式错误提示，保持输入流程顺畅。

## UI 文案

| 状态 | 文案 |
|---|---|
| idle | 分析术语与文化负载词 |
| loading | 识别中… |
| analyzed | 已分析 N 个术语与文化负载词 |
| stale | 原文已变更，重新分析 |

## 测试计划

- **更新 `inline-highlighter.test.tsx`**：验证手动触发后 glossary mark 与 cultural mark 同时渲染，glossary 与 cultural 重叠时仍 glossary 优先。
- **新增/更新 `text-editor.test.tsx`**：
  - 验证输入文本不会自动调用 `detectTerms` 或 `detectCulturalTerms`。
  - 验证点击按钮后串行调用两个接口。
  - 验证文本变更后按钮进入 `stale`。
  - 验证部分失败时仍能展示成功部分结果。
- **更新 `term-highlighter.test.tsx`**：移除自动检测相关断言，改为验证给定 `detectedTerms` 时正确渲染 badge 与 hover。

## 验收标准

- [ ] 输入文本时不再自动调用 `/api/glossary/detect`。
- [ ] 点击手动按钮后同时完成术语库检测与 LLM 文化负载词检测。
- [ ] 识别结果以内联 mark 正确展示，hover 仍显示建议译法。
- [ ] 文本变更后按钮提示 stale，可重新分析。
- [ ] 相关测试通过。
