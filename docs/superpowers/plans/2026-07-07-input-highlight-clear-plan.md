# 输入区高语境术语内联高亮手动清除实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在工作台输入区「分析术语与文化负载词」按钮旁新增常驻「清除高亮」按钮，点击后丢弃已识别的术语与文化负载词结果并回到 `idle`，使内联 `<mark>` 高亮与下方 badge 列表一并消失。

**Architecture:** 在 `glossary-store` 新增集中式 `clearHighlights` action 一次性重置 `detectedTerms` / `culturalTerms` / `culturalAnalysisState` / `hoveredTerm`；`TextEditor` 现有按钮行新增「清除高亮」按钮调用该 action，按状态与结果数量决定禁用。`InlineHighlighter`、`TermHighlighter`、后端无改动——清除经响应式 store 自动传导至渲染层。

**Tech Stack:** Next.js App Router, React, TypeScript, Zustand, Tailwind CSS, Vitest, React Testing Library, @testing-library/jest-dom.

## Global Constraints

- 不新增后端接口，不改 `InlineHighlighter` 与 `TermHighlighter` 渲染逻辑。
- 清除为丢弃语义（非临时隐藏）：重置到 `idle`，重新高亮需再次点「分析」。
- 按钮状态机沿用 `idle → loading → analyzed → stale`；清除只是把状态重置回 `idle`。
- `loading` 期间禁用清除，避免与 `analyze()` 的 store 写入竞争。
- 代码注释中英双语，重要逻辑用中文注释。
- 测试使用 Vitest + jsdom + React Testing Library，jest-dom matchers 已在 `vitest.setup.ts` 配置；mock Zustand store 沿用现有 `vi.hoisted` 响应式模式。
- 在 main 分支开发，按任务频繁提交。

---

## File Structure

| 文件 | 动作 | 说明 |
|---|---|---|
| `frontend/stores/glossary-store.ts` | 修改 | 新增 `clearHighlights` action（接口 + 实现） |
| `frontend/stores/__tests__/glossary-store.test.ts` | 创建 | `clearHighlights` 单元测试，验证四个字段重置 |
| `frontend/components/workspace/text-editor.tsx` | 修改 | 新增「清除高亮」按钮与 `clearDisabled` 禁用逻辑 |
| `frontend/components/workspace/__tests__/text-editor.test.tsx` | 修改 | mock 新增 `clearHighlights`；新增禁用条件与点击清除用例 |

---

### Task 1: glossary-store 新增 clearHighlights action（含单元测试）

**Files:**
- Modify: `frontend/stores/glossary-store.ts`
- Test: `frontend/stores/__tests__/glossary-store.test.ts`（创建）

**Interfaces:**
- Consumes: 无（纯 store 内部重置）。
- Produces: `useGlossaryStore` 新增 `clearHighlights: () => void`，调用后 `detectedTerms = []`、`culturalTerms = []`、`culturalAnalysisState = "idle"`、`hoveredTerm = null`。Task 2 的「清除高亮」按钮依赖此 action。

- [ ] **Step 1: 编写失败测试**

创建 `frontend/stores/__tests__/glossary-store.test.ts`：

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { useGlossaryStore } from "@/stores/glossary-store";
import type { DetectedTerm } from "@/stores/glossary-store";
import type { CulturalTermResult } from "@/lib/api-client";

// 已分析后的非空状态样本 — 用于验证 clearHighlights 将其全部重置
const seededGlossaryTerm: DetectedTerm = {
  source_term: "人类命运共同体",
  term_type: "political_discourse",
  risk_notes: "高风险",
  translations: {},
};

const seededCulturalTerm: CulturalTermResult = {
  term: "命运共同体",
  offset: 2,
  length: 5,
  culture_gap: "high",
  adaptation_strategy: "explanatory",
  suggested_rendering: "a community of shared future",
  reason: "政治话语",
  term_type: "cultural_metaphor",
};

describe("glossary-store clearHighlights", () => {
  beforeEach(() => {
    useGlossaryStore.setState({
      detectedTerms: [seededGlossaryTerm],
      culturalTerms: [seededCulturalTerm],
      culturalAnalysisState: "analyzed",
      hoveredTerm: "人类命运共同体",
    });
  });

  it("resets all highlight-related fields to defaults", () => {
    useGlossaryStore.getState().clearHighlights();
    const s = useGlossaryStore.getState();
    expect(s.detectedTerms).toEqual([]);
    expect(s.culturalTerms).toEqual([]);
    expect(s.culturalAnalysisState).toBe("idle");
    expect(s.hoveredTerm).toBeNull();
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && pnpm test stores/__tests__/glossary-store.test.ts`
Expected: FAIL — `useGlossaryStore.getState().clearHighlights is not a function`（action 尚未定义）。

- [ ] **Step 3: 实现 clearHighlights action**

修改 `frontend/stores/glossary-store.ts`。在 `GlossaryState` 接口中，`setCulturalAnalysisState` 之后新增一行：

```ts
  setCulturalTerms: (terms: CulturalTermResult[]) => void;
  setCulturalAnalysisState: (s: CulturalAnalysisState) => void;
  clearHighlights: () => void;
}
```

在 `create<GlossaryState>((set) => ({ ... }))` 实现中，`setCulturalAnalysisState` 之后新增：

```ts
  culturalTerms: [],
  culturalAnalysisState: "idle",
  setCulturalTerms: (culturalTerms) => set({ culturalTerms }),
  setCulturalAnalysisState: (culturalAnalysisState) =>
    set({ culturalAnalysisState }),
  // 丢弃已识别结果，回到 idle —— 重新高亮需再次手动分析
  clearHighlights: () =>
    set({
      detectedTerms: [],
      culturalTerms: [],
      culturalAnalysisState: "idle",
      hoveredTerm: null,
    }),
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd frontend && pnpm test stores/__tests__/glossary-store.test.ts`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/stores/glossary-store.ts frontend/stores/__tests__/glossary-store.test.ts
git commit -m "feat(frontend): add clearHighlights action to glossary-store"
```

---

### Task 2: TextEditor 新增「清除高亮」按钮（含组件测试）

**Files:**
- Modify: `frontend/components/workspace/text-editor.tsx`
- Modify: `frontend/components/workspace/__tests__/text-editor.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 `useGlossaryStore.clearHighlights`；既有 `detectedTerms`、`culturalTerms`、`culturalAnalysisState`。
- Produces: 「清除高亮」按钮，`disabled` 当 `culturalAnalysisState` 为 `loading`/`idle` 或两数组均为空；点击调用 `clearHighlights`。

- [ ] **Step 1: 编写失败测试**

修改 `frontend/components/workspace/__tests__/text-editor.test.tsx`。

**(a)** 将 hoisted `glossaryState` 中 `culturalAnalysisState: "idle" as const` 放宽为 `"idle" as string`，并新增 `clearHighlights` 响应式 mock。最终 hoisted 块为：

```ts
const glossaryState = vi.hoisted(() => ({
  detectedTerms: [] as any[],
  culturalTerms: [] as any[],
  culturalAnalysisState: "idle" as string,
  setDetectedTerms: vi.fn((terms: any[]) => {
    glossaryState.detectedTerms = terms;
  }),
  setCulturalTerms: vi.fn((terms: any[]) => {
    glossaryState.culturalTerms = terms;
  }),
  setCulturalAnalysisState: vi.fn((s: any) => {
    glossaryState.culturalAnalysisState = s;
  }),
  setHoveredTerm: vi.fn(),
  hoveredTerm: null,
  isLoading: false,
  setIsLoading: vi.fn(),
  clearHighlights: vi.fn(() => {
    glossaryState.detectedTerms = [];
    glossaryState.culturalTerms = [];
    glossaryState.culturalAnalysisState = "idle";
    glossaryState.hoveredTerm = null;
  }),
}));
```

**(b)** 在文件末尾追加新 `describe` 块（位于既有 `describe("TextEditor manual detection", ...)` 之后）：

```ts
describe("TextEditor clear highlights", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    glossaryState.detectedTerms = [];
    glossaryState.culturalTerms = [];
    glossaryState.culturalAnalysisState = "idle";
    glossaryState.hoveredTerm = null;
    workspaceState.input.text = "构建人类命运共同体";
    apiClient.detectTerms.mockResolvedValue({ terms: [] });
    apiClient.detectCulturalTerms.mockResolvedValue({ terms: [] });
  });

  it("clear button disabled in idle/loading/empty, enabled with results", () => {
    const { rerender } = render(<TextEditor />);
    // idle → disabled
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeDisabled();

    // analyzed 但无结果 → disabled
    glossaryState.culturalAnalysisState = "analyzed";
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeDisabled();

    // analyzed 且有结果 → enabled
    glossaryState.detectedTerms = [
      { source_term: "人类命运共同体", term_type: "political_discourse", risk_notes: "", translations: {} },
    ];
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeEnabled();

    // loading（即使有结果）→ disabled
    glossaryState.culturalAnalysisState = "loading";
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeDisabled();
  });

  it("clicking clear invokes clearHighlights and resets to idle without re-detecting", () => {
    glossaryState.culturalAnalysisState = "analyzed";
    glossaryState.detectedTerms = [
      { source_term: "人类命运共同体", term_type: "political_discourse", risk_notes: "", translations: {} },
    ];
    glossaryState.culturalTerms = [
      { term: "人类命运共同体", offset: 2, length: 7, culture_gap: "high", adaptation_strategy: "explanatory", suggested_rendering: "x", reason: "r", term_type: "cultural_metaphor" },
    ];

    const { rerender } = render(<TextEditor />);
    const clearBtn = screen.getByRole("button", { name: "清除高亮" });
    fireEvent.click(clearBtn);

    expect(glossaryState.clearHighlights).toHaveBeenCalledTimes(1);
    // 清除不触发检测接口
    expect(apiClient.detectTerms).not.toHaveBeenCalled();
    expect(apiClient.detectCulturalTerms).not.toHaveBeenCalled();

    // mock clearHighlights 已将状态重置为 idle；rerender 后「分析」按钮回到 idle 文案，清除按钮再次禁用
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "分析术语与文化负载词" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeDisabled();
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && pnpm test components/workspace/__tests__/text-editor.test.tsx`
Expected: FAIL — 找不到 name 为「清除高亮」的按钮（`Unable to find an accessible element with the role "button" and name "清除高亮"`），因为按钮尚未实现。

- [ ] **Step 3: 实现「清除高亮」按钮**

修改 `frontend/components/workspace/text-editor.tsx`。

**(a)** 在既有 store selector 区（`setCulturalAnalysisState` selector 之后）新增 `clearHighlights` selector：

```ts
  const culturalTerms = useGlossaryStore((s) => s.culturalTerms);
  const detectedTerms = useGlossaryStore((s) => s.detectedTerms);
  const culturalAnalysisState = useGlossaryStore((s) => s.culturalAnalysisState);
  const setDetectedTerms = useGlossaryStore((s) => s.setDetectedTerms);
  const setCulturalTerms = useGlossaryStore((s) => s.setCulturalTerms);
  const setCulturalAnalysisState = useGlossaryStore(
    (s) => s.setCulturalAnalysisState,
  );
  const clearHighlights = useGlossaryStore((s) => s.clearHighlights);
```

**(b)** 在 `buttonDisabled` 定义之后新增 `clearDisabled`：

```ts
  const tooLong = text.length > 5000;
  const buttonDisabled =
    !text.trim() || tooLong || culturalAnalysisState === "loading";

  // 清除高亮：仅在 analyzed/stale 且有结果时可用；loading 或无结果时禁用
  const clearDisabled =
    culturalAnalysisState === "loading" ||
    culturalAnalysisState === "idle" ||
    (detectedTerms.length + culturalTerms.length === 0);
```

**(c)** 在按钮行中「分析」按钮之后新增「清除高亮」按钮。最终按钮行结构：

```tsx
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={analyze}
          disabled={buttonDisabled}
          title={
            tooLong ? "原文过长（>5000 字），建议分段" : "识别术语与文化负载词并高亮"
          }
          className="rounded-md border border-border bg-white px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          {buttonLabel}
        </button>
        <button
          type="button"
          onClick={clearHighlights}
          disabled={clearDisabled}
          title="清除已识别的术语与文化负载词高亮"
          className="rounded-md border border-border bg-white px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          清除高亮
        </button>
      </div>
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd frontend && pnpm test components/workspace/__tests__/text-editor.test.tsx`
Expected: PASS（既有用例 + 两个新用例全部通过）。

- [ ] **Step 5: 提交**

```bash
git add frontend/components/workspace/text-editor.tsx frontend/components/workspace/__tests__/text-editor.test.tsx
git commit -m "feat(frontend): add manual clear button for input-area highlights"
```

---

### Task 3: 全量校验

**Files:** 无（仅运行校验）

- [ ] **Step 1: TypeScript 类型检查**

Run: `cd frontend && pnpm tsc --noEmit`
Expected: 无错误。

- [ ] **Step 2: 运行前端全量测试**

Run: `cd frontend && pnpm test`
Expected: PASS（允许存在与本次改动无关的既有失败）。

- [ ] **Step 3: 核对改动范围**

Run: `git diff main...HEAD`
Expected: 仅包含 `frontend/stores/glossary-store.ts`、`frontend/stores/__tests__/glossary-store.test.ts`、`frontend/components/workspace/text-editor.tsx`、`frontend/components/workspace/__tests__/text-editor.test.tsx` 的合理变更，无对 `InlineHighlighter`、`TermHighlighter` 或后端的改动。

---

## Self-Review

**1. Spec 覆盖：**
- 「清除高亮」按钮常驻于「分析」按钮旁 → Task 2 Step 3(c)。
- `idle` 或无结果禁用；`analyzed`/`stale` 且有结果可用；`loading` 禁用 → Task 2 Step 3(b) `clearDisabled` + Step 1 禁用条件测试覆盖。
- 点击后 `<mark>` 与 badge 消失、「分析」按钮回到 idle 文案 → Task 1 `clearHighlights` 重置四字段 + Task 2 Step 1 第二个用例断言 idle 文案回归。
- 清除后再次分析可恢复高亮 → 未破坏 `analyze()` 路径（Task 2 未改 `analyze`），既有 `text-editor.test.tsx` 「calls both detect endpoints」用例仍验证分析流程。
- `text-editor.test.tsx` 新增用例通过 → Task 2 Step 4。
- 无后端改动、无 `InlineHighlighter`/`TermHighlighter` 改动 → Task 3 Step 3 核对。

**2. 占位符扫描：** 无 TBD/TODO；每个代码步骤均含完整代码；无「类似 Task N」引用。

**3. 类型一致性：** `clearHighlights` 在 Task 1 接口、实现、Task 2 selector、Task 2 mock 中签名一致（`() => void`）；重置字段（`detectedTerms`、`culturalTerms`、`culturalAnalysisState`、`hoveredTerm`）在 store 实现、单元测试断言、组件 mock 三处一致。
