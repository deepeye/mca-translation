"use client";

import { useMemo, useRef, useCallback } from "react";
import { useReviewStore } from "@/stores/review-store";
import { ScoreBadge, CategoryScoreBar } from "./score-badge";
import { IssueCard } from "./issue-card";

const MARK_STYLES: Record<string, { border: string; bg: string; bgHover: string }> = {
  terminology: { border: "#0369A1", bg: "rgba(3,105,161,0.08)", bgHover: "rgba(3,105,161,0.20)" },
  cultural: { border: "#BE185D", bg: "rgba(190,24,93,0.08)", bgHover: "rgba(190,24,93,0.20)" },
  clarity: { border: "#3F6212", bg: "rgba(63,98,18,0.08)", bgHover: "rgba(63,98,18,0.20)" },
  narrative: { border: "#7C3AED", bg: "rgba(124,58,237,0.08)", bgHover: "rgba(124,58,237,0.20)" },
};

function buildSpans(translatedText: string, issues: { index: number; category: string; span: { start: number; end: number; text: string } | null }[]) {
  return issues
    .filter((i) => i.span && i.span.start >= 0 && i.span.end > i.span.start)
    .map((i) => ({
      index: i.index,
      category: i.category,
      start: i.span!.start,
      end: i.span!.end,
      text: i.span!.text,
    }))
    .sort((a, b) => a.start - b.start);
}

export function ReviewResultPanel() {
  const result = useReviewStore((s) => s.result);
  const isLoading = useReviewStore((s) => s.isLoading);
  const highlightedIndex = useReviewStore((s) => s.highlightedIssueIndex);
  const setHighlighted = useReviewStore((s) => s.setHighlightedIssue);
  const markRefs = useRef<Map<number, HTMLElement>>(new Map());

  const allIssues = useMemo(() => {
    if (!result) return [];
    let index = 0;
    return result.categories.flatMap((cat) =>
      cat.issues.map((issue) => ({ ...issue, index: index++, category: issue.category }))
    );
  }, [result]);

  const spans = useMemo(() => {
    if (!result) return [];
    const issues = allIssues.map((i, idx) => ({ index: idx, category: i.category, span: i.span }));
    return buildSpans(result.translated_text || "", issues);
  }, [result, allIssues]);

  const handleHover = useCallback((index: number) => setHighlighted(index), [setHighlighted]);
  const handleLeave = useCallback(() => setHighlighted(null), [setHighlighted]);
  const handleClick = useCallback((index: number) => {
    const el = markRefs.current.get(index);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  const content = useMemo(() => {
    if (!result) return null;
    const text = result.translated_text || "";
    if (spans.length === 0) {
      return <span className="whitespace-pre-wrap">{text}</span>;
    }

    const parts: React.ReactNode[] = [];
    let cursor = 0;

    for (const span of spans) {
      if (span.start > cursor) {
        parts.push(<span key={`t-${cursor}`}>{text.slice(cursor, span.start)}</span>);
      }

      const style = MARK_STYLES[span.category] || MARK_STYLES.clarity;
      const isHighlighted = highlightedIndex === span.index;

      parts.push(
        <mark
          key={`m-${span.index}`}
          ref={(el) => { if (el) markRefs.current.set(span.index, el); }}
          className="cursor-pointer rounded-sm pr-1 pl-1.5 transition-colors duration-150"
          style={{
            borderLeft: `3px solid ${style.border}`,
            background: isHighlighted ? style.bgHover : style.bg,
            fontWeight: isHighlighted ? 600 : 500,
            color: "inherit",
          }}
          onMouseEnter={() => handleHover(span.index)}
          onMouseLeave={handleLeave}
        >
          {span.text}
        </mark>
      );

      cursor = Math.max(cursor, span.end);
    }

    if (cursor < text.length) {
      parts.push(<span key={`t-${cursor}`}>{text.slice(cursor)}</span>);
    }

    return parts;
  }, [result?.translated_text, spans, highlightedIndex, handleHover, handleLeave]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border border-border bg-white">
        <div className="text-sm text-muted-foreground">正在进行审校分析...</div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border border-border bg-white">
        <div className="text-sm text-muted-foreground">在左侧输入内容并点击「开始审校」</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-hidden">
      {/* Score overview */}
      <div className="shrink-0 rounded-md border border-border bg-white p-4">
        <div className="flex items-center gap-4">
          <ScoreBadge score={result.overall_score} size="md" />
          <div className="flex flex-1 flex-col gap-1.5">
            {result.categories.map((cat) => (
              <CategoryScoreBar key={cat.name} name={cat.name} score={cat.score} />
            ))}
          </div>
        </div>
      </div>

      {/* Inline annotated text */}
      <div className="flex-1 min-h-0 overflow-y-auto rounded-md border border-border bg-white p-3 text-sm leading-relaxed" dir="auto">
        {content}
      </div>

      {/* Issue cards */}
      <div className="shrink-0 flex flex-col gap-1.5 overflow-y-auto max-h-[200px]">
        {allIssues.map((issue, idx) => (
          <IssueCard
            key={idx}
            issue={issue}
            index={idx}
            isHighlighted={highlightedIndex === idx}
            onHover={handleHover}
            onLeave={handleLeave}
            onClick={handleClick}
          />
        ))}
      </div>
    </div>
  );
}
