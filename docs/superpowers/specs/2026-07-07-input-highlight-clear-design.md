# 输入区高语境术语内联高亮手动清除设计

## 背景

工作台输入区存在两类高语境术语内联高亮，均由 `TextEditor` 中「分析术语与文化负载词」按钮手动触发：

- **术语库命中**（`glossary-store.detectedTerms`，来源 `/api/glossary/detect`）
- **LLM 文化负载词**（`glossary-store.culturalTerms`，来源 `/api/glossary/detect-cultural`）

二者由 `InlineHighlighter` 合并渲染为 textarea 镜像层上的 `<mark>` 区间，术语库命中另由 `TermHighlighter` 在下方以 badge 列表展示。状态机为 `idle → loading → analyzed → stale`：分析后文本变更会置 `stale`，但**已有高亮保留**。

当前没有任何手动清除入口。清掉高亮的唯一途径是重新分析（用新结果覆盖）。用户希望增加一个显式的「清除高亮」操作，丢弃已识别结果并回到 `idle`，使输入区恢复干净状态（重新高亮需再次分析）。

## 目标

- 在「分析术语与文化负载词」按钮旁新增常驻「清除高亮」按钮。
- 点击后丢弃 `detectedTerms` / `culturalTerms`，状态回到 `idle`，`<mark>` 与 badge 一并消失。
- 按钮在 `idle` 或无结果时禁用，`analyzed` / `stale` 且有结果时可用，`loading` 期间禁用。
- 复用现有 store 字段与状态机，仅新增一个集中式 `clearHighlights` action。
- 不新增后端接口，不改 `InlineHighlighter` 渲染逻辑。

## 非目标

- 不做「临时隐藏/再显示」切换（本设计为丢弃语义，非隐藏语义）。
- 不做按单个高亮区间逐条 dismiss。
- 不在文本清空、开始转译等事件上自动清除（仅手动触发）。
- 不调整后端 cultural_preprocess 或术语库检测逻辑。
- 不改 `InlineHighlighter` 的渲染与 hover Popover 内容。

## 方案选型

选用 **A. 集中式 `clearHighlights()` store action**：

- 在 `glossary-store` 新增 `clearHighlights`，一次性重置 `detectedTerms` / `culturalTerms` / `culturalAnalysisState` / `hoveredTerm`。
- `TextEditor` 现有按钮行新增「清除高亮」按钮调用该 action。
- 重置逻辑集中、命名自解释，便于独立测试。

相比在组件内联调用三个既有 setter（方案 B），集中式 action 避免「清除语义」散落到组件、避免漏重置 `hoveredTerm`，且测试只需断言一个调用。相比通用 `reset()`（方案 C），`clearHighlights` 更贴合本场景、不引入无调用方的泛化。

## 架构与组件变更

### 1. `frontend/stores/glossary-store.ts`

- `GlossaryState` 接口新增 `clearHighlights: () => void`。
- 实现一次性重置四个相关字段：

```ts
clearHighlights: () =>
  set({
    detectedTerms: [],
    culturalTerms: [],
    culturalAnalysisState: "idle",
    hoveredTerm: null,
  }),
```

重置 `hoveredTerm` 确保 `TermHighlighter` 的 hover 态不残留到对应 badge 消失之后。

### 2. `frontend/components/workspace/text-editor.tsx`

在现有按钮行（`<div className="flex items-center gap-2">`）「分析」按钮之后新增「清除高亮」按钮，样式与「分析」按钮一致：

```tsx
const clearHighlights = useGlossaryStore((s) => s.clearHighlights);
const clearDisabled =
  culturalAnalysisState === "loading" ||
  culturalAnalysisState === "idle" ||
  (detectedTerms.length + culturalTerms.length === 0);

<button
  type="button"
  onClick={clearHighlights}
  disabled={clearDisabled}
  title="清除已识别的术语与文化负载词高亮"
  className="rounded-md border border-border bg-white px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
>
  清除高亮
</button>
```

禁用条件覆盖三种「无可清除内容」情形：`idle`（从未分析）、两数组均为空（分析后无命中）、`loading`（结果在途，避免与 `analyze()` 的写入竞争）。

### 3. `frontend/components/workspace/inline-highlighter.tsx`

- 无改动。`detectedTerms` / `culturalTerms` 变空后自然不再渲染 `<mark>`，清除经响应式 store 自动传导。

### 4. `frontend/components/workspace/term-highlighter.tsx`

- 无改动。`detectedTerms` 为空时组件已 `return null`。

### 5. 后端

- 无改动。

## 数据流

1. 用户点击「分析术语与文化负载词」→ `culturalAnalysisState` = `analyzed`，`<mark>` 与 badge 渲染，「清除高亮」按钮启用。
2. 用户点击「清除高亮」→ `clearHighlights()` 将两数组置空、状态置 `idle` → `<mark>` 与 badge 消失，「清除高亮」按钮再次禁用，「分析」按钮文案回到「分析术语与文化负载词」。
3. 用户编辑文本（`stale`）后点击清除 → 同样回到 `idle`，stale 提示消失。
4. `loading` 期间点击清除 → 按钮禁用，不触发动作。

## 错误处理

- 清除为纯前端状态重置，无网络调用，无失败路径。
- `loading` 期间禁用清除，避免与 `analyze()` 的 `setDetectedTerms` / `setCulturalTerms` / `setCulturalAnalysisState` 写入竞争。

## UI 文案

| 元素 | 文案 |
|---|---|
| 清除按钮 | 清除高亮 |
| 清除按钮 title | 清除已识别的术语与文化负载词高亮 |

## 测试计划

- **更新 `text-editor.test.tsx`**：在 hoisted `glossaryState` mock 中新增 `clearHighlights: vi.fn(() => { …同步重置… })`（沿用现有响应式 setter 模式）。新增用例：
  - 初始 `idle` 时「清除高亮」按钮禁用。
  - 分析成功后按钮启用；点击后调用 `clearHighlights` 且状态重置为 `idle`。
  - 清除后「分析」按钮文案回到「分析术语与文化负载词」。
  - 清除不触发 `detectTerms` / `detectCulturalTerms`。
- **可选 `glossary-store` 单元测试**：验证 `clearHighlights` 重置四个字段。当前仓库无 `glossary-store.test.ts`，store 已由组件测试间接覆盖，此项非必需。

## 验收标准

- [ ] 「清除高亮」按钮常驻于「分析」按钮旁。
- [ ] `idle` 或无结果时禁用；`analyzed` / `stale` 且有结果时可用；`loading` 期间禁用。
- [ ] 点击后所有 `<mark>` 高亮与 badge 列表消失，「分析」按钮回到 idle 文案。
- [ ] 清除后再次分析可正常恢复高亮。
- [ ] `text-editor.test.tsx` 新增用例通过。
