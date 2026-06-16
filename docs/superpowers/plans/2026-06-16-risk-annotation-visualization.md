# 风险标注可视化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将后端已返回的 risk_annotations 数据在前端译文中可视化——内联标记 + hover Popover + 下方卡片列表 + 双向联动高亮。

**Architecture:** 纯前端变更。用 `String.indexOf()` 在译文中定位风险短语，渲染为带左侧竖线的 `<mark>` 标签；shadcn/ui Popover 显示 hover 摘要；新增 RiskDetailList 组件替代 RiskSummary；Zustand store 新增 highlightedIndex 驱动双向联动。

**Tech Stack:** React, Zustand, shadcn/ui Popover + Badge, Tailwind CSS v4

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/stores/translation-store.ts` | Modify | 新增 highlightedIndex 字段 |
| `frontend/components/workspace/translation-result.tsx` | Modify | 重写为带内联风险标记的渲染 |
| `frontend/components/workspace/risk-annotation-popover.tsx` | Create | Hover 弹出摘要气泡 |
| `frontend/components/workspace/risk-detail-list.tsx` | Create | 替代 RiskSummary：汇总条 + 卡片列表 |
| `frontend/components/workspace/risk-summary.tsx` | Delete | 被 risk-detail-list 替代 |
| `frontend/components/workspace/output-panel.tsx` | Modify | 引用 RiskDetailList 替代 RiskSummary |

---

### Task 1: Update translation-store with highlightedIndex

**Files:**
- Modify: `frontend/stores/translation-store.ts`

- [ ] **Step 1: Add highlightedIndex to LangResult interface and initial state**

Replace the full file content:

```typescript
import { create } from "zustand";

export type ResultStatus = "idle" | "streaming" | "completed" | "failed" | "partial";

export interface RiskAnnotation {
  phrase: string;
  risk_level: "low" | "medium" | "high";
  risk_type: string;
  explanation: string;
}

export interface RiskSpan {
  index: number;
  phrase: string;
  offset: number;
  length: number;
  risk_level: "low" | "medium" | "high";
  risk_type: string;
  explanation: string;
}

interface LangResult {
  status: ResultStatus;
  translatedText: string;
  riskAnnotations: RiskAnnotation[];
  acceptanceScore: number;
  highlightedIndex: number | null;
}

interface TranslationState {
  results: Record<string, LangResult>;
  setResult: (lang: string, result: Partial<LangResult>) => void;
  appendText: (lang: string, delta: string) => void;
  resetAll: () => void;
}

export const useTranslationStore = create<TranslationState>((set) => ({
  results: {},
  setResult: (lang, result) =>
    set((s) => ({
      results: { ...s.results, [lang]: { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, ...result } },
    })),
  appendText: (lang, delta) =>
    set((s) => {
      const existing = s.results[lang] || { status: "streaming" as ResultStatus, translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null };
      return { results: { ...s.results, [lang]: { ...existing, translatedText: existing.translatedText + delta, status: "streaming" } } };
    }),
  resetAll: () => set({ results: {}),
}));
```

Key changes:
- `RiskAnnotation` and `RiskSpan` exported as interfaces (not just types) so other components can import them
- `LangResult` gains `highlightedIndex: number | null`
- Default value for `highlightedIndex` is `null` in all three places (`setResult` default, `appendText` existing fallback)

- [ ] **Step 2: Verify the store compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors related to `translation-store.ts`. There may be pre-existing warnings in other files—ignore those.

- [ ] **Step 3: Commit**

```bash
git add frontend/stores/translation-store.ts
git commit -m "feat: add highlightedIndex and export RiskAnnotation/RiskSpan types to translation-store"
```

---

### Task 2: Create RiskAnnotationPopover component

**Files:**
- Create: `frontend/components/workspace/risk-annotation-popover.tsx`

- [ ] **Step 1: Write the Popover component**

Create `frontend/components/workspace/risk-annotation-popover.tsx`:

```tsx
"use client";

import { Popover, PopoverContent, PopoverTrigger, PopoverTitle, PopoverDescription } from "@/components/ui/popover";
import type { RiskAnnotation } from "@/stores/translation-store";

const RISK_STYLES: Record<string, { label: string; badgeBg: string; badgeText: string }> = {
  high: { label: "高风险", badgeBg: "#FEE2E2", badgeText: "#DC2626" },
  medium: { label: "中风险", badgeBg: "#FFEDD5", badgeText: "#C2410C" },
  low: { label: "低风险", badgeBg: "#FEF9C3", badgeText: "#A16207" },
};

interface RiskAnnotationPopoverProps {
  annotation: RiskAnnotation;
  children: React.ReactNode;
}

export function RiskAnnotationPopover({ annotation, children }: RiskAnnotationPopoverProps) {
  const style = RISK_STYLES[annotation.risk_level] || RISK_STYLES.medium;

  return (
    <Popover openDelay={150} closeDelay={150}>
      <PopoverTrigger render={children as React.ReactElement} />
      <PopoverContent side="bottom" align="start" sideOffset={6} className="w-72 p-3">
        <div className="flex items-center gap-1.5 mb-1.5">
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
            style={{ background: style.badgeBg, color: style.badgeText }}
          >
            {style.label}
          </span>
          <span className="inline-flex items-center rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[10px] text-[#475569]">
            {annotation.risk_type}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-[#334155] line-clamp-3">
          {annotation.explanation}
        </p>
      </PopoverContent>
    </Popover>
  );
}
```

Notes:
- Uses shadcn/ui `Popover` which wraps `@base-ui/react/popover`
- `openDelay` / `closeDelay` of 150ms prevents flicker on quick mouse movements
- `line-clamp-3` truncates explanation to 3 lines in the popover
- `render` prop on `PopoverTrigger` lets the `<mark>` element be the trigger directly (base-ui pattern)

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors related to `risk-annotation-popover.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/risk-annotation-popover.tsx
git commit -m "feat: add RiskAnnotationPopover component"
```

---

### Task 3: Rewrite TranslationResult with inline risk marks

**Files:**
- Modify: `frontend/components/workspace/translation-result.tsx`

- [ ] **Step 1: Rewrite the component**

Replace the full file content of `frontend/components/workspace/translation-result.tsx`:

```tsx
"use client";

import { useMemo, useRef, useCallback } from "react";
import { useTranslationStore, type RiskAnnotation, type RiskSpan } from "@/stores/translation-store";
import { RiskAnnotationPopover } from "./risk-annotation-popover";

const RISK_MARK_STYLES: Record<string, { border: string; bg: string; bgHighlight: string }> = {
  high: { border: "#EF4444", bg: "rgba(239,68,68,0.08)", bgHighlight: "rgba(239,68,68,0.20)" },
  medium: { border: "#EA580C", bg: "rgba(234,88,12,0.06)", bgHighlight: "rgba(234,88,12,0.16)" },
  low: { border: "#EAB308", bg: "rgba(234,179,8,0.06)", bgHighlight: "rgba(234,179,8,0.16)" },
};

function locateRisks(text: string, annotations: RiskAnnotation[]): RiskSpan[] {
  const usedOffsets = new Set<number>();
  return annotations
    .map((a, index) => {
      const offset = text.indexOf(a.phrase);
      if (offset === -1) return null;
      if (usedOffsets.has(offset)) return null;
      usedOffsets.add(offset);
      return { index, phrase: a.phrase, offset, length: a.phrase.length, risk_level: a.risk_level, risk_type: a.risk_type, explanation: a.explanation };
    })
    .filter((s): s is RiskSpan => s !== null)
    .sort((a, b) => a.offset - b.offset);
}

export function TranslationResult({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);
  const setResult = useTranslationStore((s) => s.setResult);
  const highlightedIndex = result?.highlightedIndex ?? null;
  const containerRef = useRef<HTMLDivElement>(null);
  const markRefs = useRef<Map<number, HTMLElement>>(new Map());

  const spans = useMemo(
    () => (result ? locateRisks(result.translatedText, result.riskAnnotations) : []),
    [result?.translatedText, result?.riskAnnotations]
  );

  const handleMarkHover = useCallback(
    (index: number) => setResult(language, { highlightedIndex: index }),
    [language, setResult]
  );
  const handleMarkLeave = useCallback(
    () => setResult(language, { highlightedIndex: null }),
    [language, setResult]
  );

  // Scroll to a specific mark when highlighted from the list
  const scrollToMark = useCallback((index: number) => {
    const el = markRefs.current.get(index);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  // Expose scrollToMark via ref for parent (RiskDetailList) to call
  // We store it on the result so OutputPanel can pass it down
  // Simpler: use a custom event
  const handleScrollRequest = useCallback(
    (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.language === language && typeof detail?.index === "number") {
        scrollToMark(detail.index);
      }
    },
    [language, scrollToMark]
  );

  // Listen for scroll requests from RiskDetailList
  if (typeof window !== "undefined") {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { useEffect } = require("react");
    useEffect(() => {
      window.addEventListener("scroll-to-risk-mark", handleScrollRequest);
      return () => window.removeEventListener("scroll-to-risk-mark", handleScrollRequest);
    }, [handleScrollRequest]);
  }

  if (!result) {
    return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">请在左侧选择目标语言并开始转译</div>;
  }
  if (result.status === "idle") {
    return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">等待转译...</div>;
  }
  if (result.status === "failed") {
    return <div className="flex h-full items-center justify-center text-sm text-danger">转译失败，请重试</div>;
  }

  // Build segmented text with <mark> tags for risk phrases
  const content = useMemo(() => {
    if (!result.translatedText && result.status === "streaming") {
      return <span>正在生成...</span>;
    }
    if (spans.length === 0) {
      return <span>{result.translatedText}</span>;
    }

    const parts: React.ReactNode[] = [];
    let cursor = 0;

    for (const span of spans) {
      // Text before this span
      if (span.offset > cursor) {
        parts.push(<span key={`t-${cursor}`}>{result.translatedText.slice(cursor, span.offset)}</span>);
      }

      const style = RISK_MARK_STYLES[span.risk_level] || RISK_MARK_STYLES.medium;
      const isHighlighted = highlightedIndex === span.index;

      parts.push(
        <RiskAnnotationPopover key={`m-${span.index}`} annotation={span}>
          <mark
            ref={(el) => { if (el) markRefs.current.set(span.index, el); }}
            className="cursor-pointer rounded-sm pr-1 pl-1.5 transition-colors duration-150"
            style={{
              borderLeft: `3px solid ${style.border}`,
              background: isHighlighted ? style.bgHighlight : style.bg,
              fontWeight: isHighlighted ? 600 : 500,
              color: "inherit",
            }}
            onMouseEnter={() => handleMarkHover(span.index)}
            onMouseLeave={handleMarkLeave}
          >
            {span.phrase}
          </mark>
        </RiskAnnotationPopover>
      );

      cursor = span.offset + span.length;
    }

    // Remaining text after last span
    if (cursor < result.translatedText.length) {
      parts.push(<span key={`t-${cursor}`}>{result.translatedText.slice(cursor)}</span>);
    }

    return parts;
  }, [result.translatedText, spans, highlightedIndex, handleMarkHover, handleMarkLeave]);

  return (
    <div ref={containerRef} className="h-full overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-white p-3 text-sm leading-relaxed text-foreground">
      {content}
    </div>
  );
}
```

Key design decisions:
- `locateRisks()` uses `String.indexOf()` to find each phrase, sorts by offset, avoids overlap
- `markRefs` map stores DOM references for scroll-into-view
- Custom event `scroll-to-risk-mark` lets `RiskDetailList` request scrolling without prop drilling
- Highlighted state reads from `highlightedIndex` in store, drives background opacity ×2 and font-weight 600
- The `useEffect` for custom events is guarded by `typeof window` check (SSR safety)
- Popover wraps each `<mark>` via `RiskAnnotationPopover`

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -30`

Expected: No errors related to `translation-result.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/translation-result.tsx
git commit -m "feat: rewrite TranslationResult with inline risk marks and hover popover"
```

---

### Task 4: Create RiskDetailList component

**Files:**
- Create: `frontend/components/workspace/risk-detail-list.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/components/workspace/risk-detail-list.tsx`:

```tsx
"use client";

import { useCallback } from "react";
import { useTranslationStore, type RiskAnnotation } from "@/stores/translation-store";

const RISK_BADGE_STYLES: Record<string, { label: string; badgeBg: string; badgeText: string; borderColor: string }> = {
  high: { label: "高风险", badgeBg: "#FEE2E2", badgeText: "#DC2626", borderColor: "#FCA5A5" },
  medium: { label: "中风险", badgeBg: "#FFEDD5", badgeText: "#C2410C", borderColor: "#FDBA74" },
  low: { label: "低风险", badgeBg: "#FEF9C3", badgeText: "#A16207", borderColor: "#FDE68A" },
};

function RiskDetailCard({
  annotation,
  index,
  isHighlighted,
  onHover,
  onLeave,
  onClick,
}: {
  annotation: RiskAnnotation;
  index: number;
  isHighlighted: boolean;
  onHover: (index: number) => void;
  onLeave: () => void;
  onClick: (index: number) => void;
}) {
  const style = RISK_BADGE_STYLES[annotation.risk_level] || RISK_BADGE_STYLES.medium;

  return (
    <div
      className="cursor-pointer rounded-md border p-2.5 transition-colors duration-150"
      style={{
        background: "white",
        borderColor: isHighlighted ? style.borderColor : "#E2E8F0",
      }}
      onMouseEnter={() => onHover(index)}
      onMouseLeave={onLeave}
      onClick={() => onClick(index)}
    >
      <div className="flex flex-wrap items-center gap-1.5 mb-1">
        <span
          className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
          style={{ background: style.badgeBg, color: style.badgeText }}
        >
          {style.label}
        </span>
        <span className="text-xs font-medium text-[#134E4A]">&ldquo;{annotation.phrase}&rdquo;</span>
        <span className="inline-flex items-center rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[9px] text-[#475569]">
          {annotation.risk_type}
        </span>
      </div>
      <p className="text-[11px] leading-relaxed text-[#64748B]">{annotation.explanation}</p>
    </div>
  );
}

export function RiskDetailList({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);
  const setResult = useTranslationStore((s) => s.setResult);

  const annotations = result?.riskAnnotations ?? [];
  const highlightedIndex = result?.highlightedIndex ?? null;

  const handleHover = useCallback(
    (index: number) => setResult(language, { highlightedIndex: index }),
    [language, setResult]
  );
  const handleLeave = useCallback(
    () => setResult(language, { highlightedIndex: null }),
    [language, setResult]
  );
  const handleClick = useCallback((index: number) => {
    window.dispatchEvent(new CustomEvent("scroll-to-risk-mark", { detail: { language, index } }));
  }, [language]);

  if (!annotations.length) return null;

  const counts = { high: 0, medium: 0, low: 0 };
  for (const a of annotations) {
    counts[a.risk_level] = (counts[a.risk_level] || 0) + 1;
  }

  return (
    <div className="flex flex-col gap-1.5">
      {/* Summary bar — same style as old RiskSummary */}
      <div className="rounded border-l-3 border-terracotta bg-amber-50 px-3 py-2 text-xs text-amber-800">
        <span className="font-medium">风险标注：</span>
        {annotations.length} 处表达在目标受众中存在认知风险
        {counts.high > 0 && <span className="ml-2 text-danger">{counts.high} 高风险</span>}
        {counts.medium > 0 && <span className="ml-2 text-terracotta">{counts.medium} 中风险</span>}
        {counts.low > 0 && <span className="ml-2 text-amber-600">{counts.low} 低风险</span>}
      </div>

      {/* Detail cards */}
      <div className="flex flex-col gap-1.5">
        {annotations.map((a, index) => (
          <RiskDetailCard
            key={index}
            annotation={a}
            index={index}
            isHighlighted={highlightedIndex === index}
            onHover={handleHover}
            onLeave={handleLeave}
            onClick={handleClick}
          />
        ))}
      </div>
    </div>
  );
}
```

Key design decisions:
- Summary bar preserves the exact same visual as the old `RiskSummary` (border-left terracotta, amber bg)
- `RiskDetailCard` is an internal component, not exported
- Hover sets `highlightedIndex` in store → `TranslationResult` reads it and highlights the `<mark>`
- Click dispatches `scroll-to-risk-mark` custom event → `TranslationResult` listens and scrolls
- Card border changes to risk color when highlighted

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Expected: No errors related to `risk-detail-list.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/workspace/risk-detail-list.tsx
git commit -m "feat: add RiskDetailList component with card list and highlight linking"
```

---

### Task 5: Wire up OutputPanel and delete RiskSummary

**Files:**
- Modify: `frontend/components/workspace/output-panel.tsx`
- Delete: `frontend/components/workspace/risk-summary.tsx`

- [ ] **Step 1: Update OutputPanel to use RiskDetailList**

Replace the full content of `frontend/components/workspace/output-panel.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useTranslationStore } from "@/stores/translation-store";
import { LanguageTabs } from "./language-tabs";
import { TranslationResult } from "./translation-result";
import { RiskDetailList } from "./risk-detail-list";
import { ResultActions } from "./result-actions";

export function OutputPanel() {
  const languages = useWorkspaceStore((s) => s.languages);
  const [activeLang, setActiveLang] = useState(languages[0] || "en-GB");
  const result = useTranslationStore((s) => s.results[activeLang]);

  // Sync active tab when languages change
  if (!languages.includes(activeLang) && languages.length > 0) {
    setActiveLang(languages[0]);
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <LanguageTabs activeLang={activeLang} onSwitch={setActiveLang} />
      <TranslationResult language={activeLang} />
      <RiskDetailList language={activeLang} />
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
}
```

Change: `RiskSummary` import → `RiskDetailList` import, component usage updated. Everything else identical.

- [ ] **Step 2: Delete the old RiskSummary file**

```bash
rm frontend/components/workspace/risk-summary.tsx
```

- [ ] **Step 3: Verify the app builds**

Run: `cd frontend && pnpm build 2>&1 | tail -20`

Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/workspace/output-panel.tsx
git rm frontend/components/workspace/risk-summary.tsx
git commit -m "feat: wire RiskDetailList into OutputPanel, remove old RiskSummary"
```

---

### Task 6: Smoke test and fix any issues

**Files:**
- Possibly modify any files from Tasks 1-5 if issues found

- [ ] **Step 1: Start the dev server and check for runtime errors**

Run: `cd frontend && pnpm dev`

Open http://localhost:3000 in browser, log in with admin/admin123, submit a translation, and verify:

1. ✅ Risk phrases appear in the translated text with left-border marks (red for high, orange for medium)
2. ✅ Hovering a mark shows a Popover with risk level badge + type + explanation
3. ✅ Below the translation, the summary bar appears ("风险标注：2 处...")
4. ✅ Below the summary, risk detail cards appear with full explanations
5. ✅ Hovering a card highlights the corresponding mark in the translation (background darkens, font bolds)
6. ✅ Hovering a mark in translation highlights the corresponding card (border changes color)
7. ✅ Clicking a card scrolls the translation to the corresponding mark
8. ✅ No console errors related to our components

- [ ] **Step 2: Fix any issues found during smoke test**

If any of the above checks fail, diagnose and fix. Common issues:
- Popover positioning: adjust `side`, `align`, `sideOffset` props
- `indexOf` not finding phrase: check if whitespace/encoding differs between API response and rendered text
- Custom event not received: verify event name matches exactly (`scroll-to-risk-mark`)

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "fix: address smoke test issues for risk annotation visualization"
```

(Only if changes were needed — skip this step if everything works.)
