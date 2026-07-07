# 输入区政治话语/文化隐喻手动触发识别实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将输入区政治话语/文化隐喻识别从自动触发改为统一手动触发，复用现有后端接口，保持内联高亮与 hover 行为不变。

**Architecture:** 移除 `TermHighlighter` 的 800ms 自动检测逻辑，改为纯展示组件；改造 `TextEditor` 中的手动按钮为统一入口，串行调用 `/api/glossary/detect` 与 `/api/glossary/detect-cultural`；`InlineHighlighter` 与后端无改动。

**Tech Stack:** Next.js App Router, React, TypeScript, Zustand, Tailwind CSS, Vitest, React Testing Library.

## Global Constraints

- 不新增后端接口，复用现有 `/api/glossary/detect` 与 `/api/glossary/detect-cultural`。
- 不修改 `InlineHighlighter` 渲染逻辑与 hover Popover 内容。
- 不在输入区新增阻断式错误提示。
- 按钮状态机沿用 `idle → loading → analyzed → stale`。
- 测试使用 Vitest + jsdom + React Testing Library，mock Zustand store。

---

## File Structure

| 文件 | 动作 | 说明 |
|---|---|---|
| `frontend/components/workspace/term-highlighter.tsx` | 修改 | 移除自动检测，改为纯展示组件 |
| `frontend/components/workspace/text-editor.tsx` | 修改 | 统一手动触发入口，串行调用两个检测接口 |
| `frontend/components/workspace/__tests__/inline-highlighter.test.tsx` | 修改 | 新增 glossary + cultural 同时渲染的断言 |
| `frontend/components/workspace/__tests__/text-editor.test.tsx` | 创建 | 验证手动触发、stale 状态、失败降级 |
| `frontend/components/workspace/__tests__/term-highlighter.test.tsx` | 创建 | 验证 badge 渲染与 hover tooltip |

---

### Task 1: 移除 TermHighlighter 的自动检测

**Files:**
- Modify: `frontend/components/workspace/term-highlighter.tsx`
- Test: `frontend/components/workspace/__tests__/term-highlighter.test.tsx`（Task 5 创建）

**Interfaces:**
- Consumes: `useGlossaryStore` 的 `detectedTerms`、`hoveredTerm`、`setHoveredTerm`；`useWorkspaceStore` 的 `activeLanguage`。
- Produces: 渲染 glossary badge 列表与 hover tooltip；不再触发任何 API 调用。

- [ ] **Step 1: 修改 `TermHighlighter` 组件**

删除 `useEffect`、`useRef`、`useCallback`、`apiClient`、`detect` 自动检测逻辑；删除 `text` prop（检测不再依赖输入文本变化）；保留 badge 渲染与 hover tooltip。

`frontend/components/workspace/term-highlighter.tsx` 最终内容：

```tsx
"use client";

import { useGlossaryStore } from "@/stores/glossary-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { LANGUAGE_LABELS } from "@/lib/languages";
import {
  DEFAULT_TERM_TYPE_BADGE_CLASS,
  DEFAULT_TERM_TYPE_LABEL,
  SYSTEM_GLOSSARY_TERM_TYPE_LABELS,
  TERM_TYPE_BADGE_CLASS,
} from "@/lib/glossary-categories";

interface TermHighlighterProps {
  containerClassName?: string;
}

export function TermHighlighter({ containerClassName = "" }: TermHighlighterProps) {
  const detectedTerms = useGlossaryStore((s) => s.detectedTerms);
  const hoveredTerm = useGlossaryStore((s) => s.hoveredTerm);
  const setHoveredTerm = useGlossaryStore((s) => s.setHoveredTerm);
  const activeLang = useWorkspaceStore((s) => s.activeLanguage);

  if (detectedTerms.length === 0) return null;

  return (
    <div className={`flex flex-wrap gap-1.5 ${containerClassName}`}>
      {detectedTerms.map((term) => {
        const badgeClass = TERM_TYPE_BADGE_CLASS[term.term_type] || DEFAULT_TERM_TYPE_BADGE_CLASS;
        const label = SYSTEM_GLOSSARY_TERM_TYPE_LABELS[term.term_type] || DEFAULT_TERM_TYPE_LABEL;
        return (
          <div
            key={term.source_term}
            className="relative"
            onMouseEnter={() => setHoveredTerm(term.source_term)}
            onMouseLeave={() => setHoveredTerm(null)}
          >
            <span
              className={`inline-flex cursor-default items-center rounded px-1.5 py-0.5 text-xs font-medium transition-colors ${badgeClass}`}
            >
              {term.source_term}
            </span>
            {hoveredTerm === term.source_term && (
              <div className="absolute bottom-full left-0 z-50 mb-1 w-64 rounded-md border border-border bg-white p-2 shadow-lg">
                <div className="text-xs font-semibold text-foreground">{term.source_term}</div>
                <div className="mt-1 text-xs text-muted-foreground">{label}</div>
                {term.risk_notes && (
                  <div className="mt-1 text-xs text-orange-600">⚠ {term.risk_notes}</div>
                )}
                {(() => {
                  const translation = term.translations[activeLang] ?? term.translations["en-GB"];
                  const labelCode = term.translations[activeLang] ? activeLang : "en-GB";
                  if (translation) {
                    return (
                      <div className="mt-1 text-xs text-teal-700">
                        {LANGUAGE_LABELS[labelCode] ?? "英语"}：{translation.preferred}
                      </div>
                    );
                  }
                  return null;
                })()}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: 运行 Task 1 相关测试（此时 Task 5 测试尚未创建，先运行现有 inline-highlighter 测试确保无回归）**

Run: `cd frontend && pnpm test components/workspace/__tests__/inline-highlighter.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/term-highlighter.tsx
git commit -m "refactor(frontend): remove auto-detection from TermHighlighter"
```

---

### Task 2: 统一手动触发入口

**Files:**
- Modify: `frontend/components/workspace/text-editor.tsx`
- Test: `frontend/components/workspace/__tests__/text-editor.test.tsx`（Task 4 创建）

**Interfaces:**
- Consumes: `useWorkspaceStore` 的 `input.text`、`input.culturalSphere`、`input.audienceType`、`input.genre`；`useGlossaryStore` 的 `culturalTerms`、`culturalAnalysisState`、`setDetectedTerms`、`setCulturalTerms`、`setCulturalAnalysisState`；`apiClient.detectTerms`、`apiClient.detectCulturalTerms`。
- Produces: 点击按钮后串行调用两个检测接口，结果分别写入 store；按钮文案与状态按 `idle/loading/analyzed/stale` 更新。

- [ ] **Step 1: 修改 `TextEditor` 组件**

从 `useGlossaryStore` 新增读取 `setDetectedTerms`；修改 `analyze` 函数为统一入口，串行调用 `detectTerms` 与 `detectCulturalTerms`，任一接口失败独立降级；更新按钮文案；移除 `<TermHighlighter text={text} ... />` 中的 `text` prop。

修改后的 `frontend/components/workspace/text-editor.tsx` 完整内容：

```tsx
"use client";

import { useEffect, useRef } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useGlossaryStore } from "@/stores/glossary-store";
import { apiClient } from "@/lib/api-client";
import { InlineHighlighter } from "./inline-highlighter";
import { TermHighlighter } from "./term-highlighter";

export function TextEditor() {
  const text = useWorkspaceStore((s) => s.input.text);
  const culturalSphere = useWorkspaceStore((s) => s.input.culturalSphere);
  const audienceType = useWorkspaceStore((s) => s.input.audienceType);
  const genre = useWorkspaceStore((s) => s.input.genre);

  const culturalTerms = useGlossaryStore((s) => s.culturalTerms);
  const detectedTerms = useGlossaryStore((s) => s.detectedTerms);
  const culturalAnalysisState = useGlossaryStore((s) => s.culturalAnalysisState);
  const setDetectedTerms = useGlossaryStore((s) => s.setDetectedTerms);
  const setCulturalTerms = useGlossaryStore((s) => s.setCulturalTerms);
  const setCulturalAnalysisState = useGlossaryStore(
    (s) => s.setCulturalAnalysisState,
  );

  const stateRef = useRef(culturalAnalysisState);
  stateRef.current = culturalAnalysisState;
  useEffect(() => {
    if (stateRef.current === "analyzed") setCulturalAnalysisState("stale");
  }, [text, setCulturalAnalysisState]);

  const analyze = async () => {
    setCulturalAnalysisState("loading");

    let glossaryTerms: typeof detectedTerms = [];
    let culturalTermsResult: typeof culturalTerms = [];
    let glossarySuccess = false;
    let culturalSuccess = false;

    try {
      const result = await apiClient.detectTerms(text);
      glossaryTerms = result.terms || [];
      glossarySuccess = true;
    } catch {
      glossaryTerms = [];
    }

    try {
      const result = await apiClient.detectCulturalTerms({
        text,
        cultural_sphere: culturalSphere,
        audience_type: audienceType,
        genre,
      });
      culturalTermsResult = result.terms || [];
      culturalSuccess = true;
    } catch {
      culturalTermsResult = [];
    }

    setDetectedTerms(glossaryTerms);
    setCulturalTerms(culturalTermsResult);
    setCulturalAnalysisState(glossarySuccess || culturalSuccess ? "analyzed" : "idle");
  };

  const tooLong = text.length > 5000;
  const buttonDisabled =
    !text.trim() || tooLong || culturalAnalysisState === "loading";

  const buttonLabel = (() => {
    switch (culturalAnalysisState) {
      case "loading":
        return "识别中…";
      case "analyzed":
        return `已分析 ${detectedTerms.length + culturalTerms.length} 个术语与文化负载词`;
      case "stale":
        return "原文已变更，重新分析";
      default:
        return "分析术语与文化负载词";
    }
  })();

  return (
    <div className="relative flex flex-1 flex-col gap-2">
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
      </div>

      <div className="flex-1">
        <InlineHighlighter />
      </div>

      <TermHighlighter containerClassName="px-1" />

      <div className="absolute bottom-2 right-3 text-xs text-muted-foreground">
        {text.length} / 10000
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 运行 TypeScript 检查**

Run: `cd frontend && pnpm tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/text-editor.tsx
git commit -m "feat(frontend): unify manual input-area term and cultural detection"
```

---

### Task 3: 更新 InlineHighlighter 测试

**Files:**
- Modify: `frontend/components/workspace/__tests__/inline-highlighter.test.tsx`

**Interfaces:**
- Consumes: 已有的 mock store 数据；验证 glossary mark 与 cultural mark 同时存在。

- [ ] **Step 1: 在现有测试文件末尾新增一个测试用例**

```tsx
  it("glossary 与 cultural 同时存在时各自渲染 mark", () => {
    setText("一带一路与构建人类命运共同体");
    setGlossary([
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
        },
      },
    ]);
    setCultural([
      {
        term: "人类命运共同体",
        offset: 7,
        length: 7,
        culture_gap: "high",
        adaptation_strategy: "explanatory",
        suggested_rendering: "a community with a shared future for mankind",
        reason: "政治话语",
        term_type: "cultural_metaphor",
      },
    ]);
    const { container } = render(<InlineHighlighter />);
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(2);
    expect(marks[0].textContent).toBe("一带一路");
    expect(marks[1].textContent).toBe("人类命运共同体");
  });
```

- [ ] **Step 2: 运行测试**

Run: `cd frontend && pnpm test components/workspace/__tests__/inline-highlighter.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/__tests__/inline-highlighter.test.tsx
git commit -m "test(frontend): assert glossary and cultural marks render together"
```

---

### Task 4: 创建 TextEditor 测试

**Files:**
- Create: `frontend/components/workspace/__tests__/text-editor.test.tsx`

**Interfaces:**
- Consumes: mock `useWorkspaceStore`、`useGlossaryStore`、`apiClient`。
- Produces: 验证手动触发调用两个接口、文本变更进入 stale、失败降级。

- [ ] **Step 1: 创建测试文件**

`frontend/components/workspace/__tests__/text-editor.test.tsx` 内容：

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const workspaceState = vi.hoisted(() => ({
  input: {
    text: "构建人类命运共同体",
    culturalSphere: "western_english",
    audienceType: "general_public",
    genre: "political",
  },
}));

const glossaryState = vi.hoisted(() => ({
  detectedTerms: [] as any[],
  culturalTerms: [] as any[],
  culturalAnalysisState: "idle" as const,
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
}));

const apiClient = vi.hoisted(() => ({
  detectTerms: vi.fn(),
  detectCulturalTerms: vi.fn(),
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(workspaceState) : workspaceState,
  ),
}));

vi.mock("@/stores/glossary-store", () => ({
  useGlossaryStore: vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(glossaryState) : glossaryState,
  ),
}));

vi.mock("@/lib/api-client", () => ({ apiClient }));

// InlineHighlighter and TermHighlighter render nothing with empty stores
vi.mock("../inline-highlighter", () => ({ InlineHighlighter: () => <div data-testid="inline-highlighter" /> }));
vi.mock("../term-highlighter", () => ({ TermHighlighter: () => <div data-testid="term-highlighter" /> }));

import { TextEditor } from "../text-editor";

describe("TextEditor manual detection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    glossaryState.detectedTerms = [];
    glossaryState.culturalTerms = [];
    glossaryState.culturalAnalysisState = "idle";
    workspaceState.input.text = "构建人类命运共同体";
    apiClient.detectTerms.mockResolvedValue({ terms: [] });
    apiClient.detectCulturalTerms.mockResolvedValue({ terms: [] });
  });

  it("does not auto-detect on render", () => {
    render(<TextEditor />);
    expect(apiClient.detectTerms).not.toHaveBeenCalled();
    expect(apiClient.detectCulturalTerms).not.toHaveBeenCalled();
  });

  it("calls both detect endpoints when analyze button is clicked", async () => {
    apiClient.detectTerms.mockResolvedValue({
      terms: [{ source_term: "人类命运共同体", term_type: "political_discourse", risk_notes: "", translations: {} }],
    });
    apiClient.detectCulturalTerms.mockResolvedValue({
      terms: [{ term: "人类命运共同体", offset: 2, length: 7, culture_gap: "high", adaptation_strategy: "explanatory", suggested_rendering: "x", reason: "r", term_type: "cultural_metaphor" }],
    });

    render(<TextEditor />);
    const btn = screen.getByRole("button", { name: /分析术语与文化负载词/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(apiClient.detectTerms).toHaveBeenCalledWith("构建人类命运共同体");
      expect(apiClient.detectCulturalTerms).toHaveBeenCalledWith({
        text: "构建人类命运共同体",
        cultural_sphere: "western_english",
        audience_type: "general_public",
        genre: "political",
      });
    });

    expect(glossaryState.setDetectedTerms).toHaveBeenCalled();
    expect(glossaryState.setCulturalTerms).toHaveBeenCalled();
    expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("analyzed");
  });

  it("sets stale state when text changes after analyzed", async () => {
    apiClient.detectTerms.mockResolvedValue({ terms: [] });
    apiClient.detectCulturalTerms.mockResolvedValue({ terms: [] });

    const { rerender } = render(<TextEditor />);
    fireEvent.click(screen.getByRole("button", { name: /分析术语与文化负载词/ }));

    await waitFor(() => {
      expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("analyzed");
    });

    // Simulate external text change
    workspaceState.input.text = "构建人类命运共同体和一带一路";
    rerender(<TextEditor />);

    await waitFor(() => {
      expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("stale");
    });
  });

  it("falls back to idle when both detections fail", async () => {
    apiClient.detectTerms.mockRejectedValue(new Error("fail"));
    apiClient.detectCulturalTerms.mockRejectedValue(new Error("fail"));

    render(<TextEditor />);
    fireEvent.click(screen.getByRole("button", { name: /分析术语与文化负载词/ }));

    await waitFor(() => {
      expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("idle");
    });
  });

  it("shows analyzed state when only glossary detection succeeds", async () => {
    apiClient.detectTerms.mockResolvedValue({
      terms: [{ source_term: "一带一路", term_type: "political_discourse", risk_notes: "", translations: {} }],
    });
    apiClient.detectCulturalTerms.mockRejectedValue(new Error("fail"));

    render(<TextEditor />);
    fireEvent.click(screen.getByRole("button", { name: /分析术语与文化负载词/ }));

    await waitFor(() => {
      expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("analyzed");
    });
  });
});
```

- [ ] **Step 2: 运行测试**

Run: `cd frontend && pnpm test components/workspace/__tests__/text-editor.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/__tests__/text-editor.test.tsx
git commit -m "test(frontend): add TextEditor manual detection tests"
```

---

### Task 5: 创建 TermHighlighter 测试

**Files:**
- Create: `frontend/components/workspace/__tests__/term-highlighter.test.tsx`

**Interfaces:**
- Consumes: mock `useGlossaryStore`、`useWorkspaceStore`。
- Produces: 验证给定 `detectedTerms` 时渲染 badge 与 hover tooltip；空数据时返回 null。

- [ ] **Step 1: 创建测试文件**

`frontend/components/workspace/__tests__/term-highlighter.test.tsx` 内容：

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Reactive mock state — listeners allow setHoveredTerm to trigger re-renders,
// 模拟 Zustand store 的订阅机制，使 hover 状态变更能驱动组件重渲染。
const glossaryState = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  return {
    detectedTerms: [] as any[],
    hoveredTerm: null as string | null,
    listeners,
    setHoveredTerm: vi.fn((term: string | null) => {
      glossaryState.hoveredTerm = term;
      glossaryState.listeners.forEach((l) => l());
    }),
  };
});

const workspaceState = vi.hoisted(() => ({
  activeLanguage: "en-GB",
}));

vi.mock("@/stores/glossary-store", async () => {
  const { useSyncExternalStore } = await import("react");
  return {
    useGlossaryStore: vi.fn((selector?: (s: unknown) => unknown) => {
      // useSyncExternalStore 订阅 listeners，当 hoveredTerm 变化时触发重渲染
      useSyncExternalStore(
        (cb: () => void) => {
          glossaryState.listeners.add(cb);
          return () => {
            glossaryState.listeners.delete(cb);
          };
        },
        () => glossaryState.hoveredTerm,
      );
      return selector ? selector(glossaryState) : glossaryState;
    }),
  };
});

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(workspaceState) : workspaceState,
  ),
}));

import { TermHighlighter } from "../term-highlighter";

describe("TermHighlighter", () => {
  beforeEach(() => {
    glossaryState.detectedTerms = [];
    glossaryState.hoveredTerm = null;
    glossaryState.listeners.clear();
    workspaceState.activeLanguage = "en-GB";
  });

  it("renders nothing when no terms detected", () => {
    const { container } = render(<TermHighlighter />);
    expect(container.firstChild).toBeNull();
  });

  it("renders badge for each detected term", () => {
    glossaryState.detectedTerms = [
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险政治话语",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
        },
      },
    ];
    render(<TermHighlighter />);
    expect(screen.getByText("一带一路")).toBeInTheDocument();
  });

  it("shows hover tooltip with preferred translation", () => {
    glossaryState.detectedTerms = [
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
        },
      },
    ];
    render(<TermHighlighter />);
    fireEvent.mouseEnter(screen.getByText("一带一路"));
    expect(screen.getByText(/英语/)).toBeInTheDocument();
    expect(screen.getByText(/BRI/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试**

Run: `cd frontend && pnpm test components/workspace/__tests__/term-highlighter.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/__tests__/term-highlighter.test.tsx
git commit -m "test(frontend): add TermHighlighter pure-render tests"
```

---

## 集成验证

- [ ] **Step 1: 运行相关组件测试**

Run: `cd frontend && pnpm test components/workspace/__tests__`
Expected: 所有测试 PASS

- [ ] **Step 2: 运行前端完整测试套件**

Run: `cd frontend && pnpm test`
Expected: PASS（允许存在与本次改动无关的既有失败）

- [ ] **Step 3: 运行 TypeScript 检查**

Run: `cd frontend && pnpm tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: 提交集成验证结果（如无变更则无需提交）**

若测试全部通过，可继续下一步；若需修复，单独 commit 每个修复。

---

## 最终审查

- [ ] **Step 1: 检查 diff**

Run: `git diff main...HEAD`
Expected: 仅包含 `text-editor.tsx`、`term-highlighter.tsx` 及三个测试文件的合理变更。

- [ ] **Step 2: 邀请代码审查**

使用 `superpowers:requesting-code-review` 或人工审查，确认：
- 输入文本不再自动触发检测。
- 手动按钮同时调用两个接口。
- hover 行为保持现有设计。
- 测试覆盖新增行为。

---

## 自审清单

1. **Spec coverage:**
   - 自动检测移除 → Task 1
   - 统一手动触发 → Task 2
   - hover 行为不变 → InlineHighlighter 未改动
   - 失败降级 → Task 2 错误处理 + Task 4 测试
   - 测试计划 → Task 3/4/5
2. **Placeholder scan:** 无 TBD/TODO/"稍后实现"。
3. **Type consistency:** `TermHighlighterProps` 移除 `text`；`TextEditor` 调用 `setDetectedTerms`；store 接口与现有 `glossary-store.ts` 一致。
