"use client";

import { useMemo, useRef, useCallback, useEffect } from "react";
import { useTranslationStore, type RiskAnnotation, type RiskSpan } from "@/stores/translation-store";
import { RiskAnnotationPopover } from "./risk-annotation-popover";
import { CulturalAdaptationPanel } from "./cultural-adaptation-panel";

const RISK_MARK_STYLES: Record<string, { border: string; bg: string; bgHighlight: string }> = {
  high: { border: "var(--color-risk-high)", bg: "var(--color-risk-high-bg)", bgHighlight: "var(--color-risk-high-bg-highlight)" },
  medium: { border: "var(--color-risk-medium)", bg: "var(--color-risk-medium-bg)", bgHighlight: "var(--color-risk-medium-bg-highlight)" },
  low: { border: "var(--color-risk-low)", bg: "var(--color-risk-low-bg)", bgHighlight: "var(--color-risk-low-bg-highlight)" },
  accepted: { border: "var(--color-risk-accepted)", bg: "var(--color-risk-accepted-bg)", bgHighlight: "var(--color-risk-accepted-bg-highlight)" },
  dismissed: { border: "var(--color-risk-dismissed)", bg: "var(--color-risk-dismissed-bg)", bgHighlight: "var(--color-risk-dismissed-bg-highlight)" },
};

function locateRisks(text: string, annotations: RiskAnnotation[]): RiskSpan[] {
  const usedOffsets = new Set<number>();
  const spans: RiskSpan[] = [];
  annotations.forEach((a, index) => {
    const status = a.status || "open";
    const searchPhrase = status === "accepted" && a.accepted_suggestion ? a.accepted_suggestion : a.phrase || "";
    const offset = a.offset != null && a.offset >= 0 ? a.offset : text.indexOf(searchPhrase);
    if (offset === -1 || usedOffsets.has(offset)) return;
    usedOffsets.add(offset);
    spans.push({
      index,
      phrase: searchPhrase,
      offset,
      length: searchPhrase.length,
      risk_level: a.risk_level,
      risk_type: a.risk_type,
      explanation: a.explanation,
      status,
    });
  });
  return spans.sort((a, b) => a.offset - b.offset);
}

export function TranslationResult({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);
  const setResult = useTranslationStore((s) => s.setResult);
  const highlightedIndex = result?.highlightedIndex ?? null;
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

  // Listen for scroll requests from RiskDetailList
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.language === language && typeof detail?.index === "number") {
        const el = markRefs.current.get(detail.index);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    };
    window.addEventListener("scroll-to-risk-mark", handler);
    return () => window.removeEventListener("scroll-to-risk-mark", handler);
  }, [language]);

  // Build segmented text with <mark> tags for risk phrases
  // Must be called before any early returns (Rules of Hooks)
  const content = useMemo(() => {
    if (!result) return null;
    if (result.status === "idle") return null;
    if (result.status === "failed") return null;
    if (!result.translatedText && result.status === "streaming") {
      return <span>正在生成...</span>;
    }
    if (spans.length === 0) {
      return <span>{result.translatedText}</span>;
    }

    const parts: React.ReactNode[] = [];
    let cursor = 0;

    for (const span of spans) {
      if (span.offset > cursor) {
        parts.push(<span key={`t-${cursor}`}>{result.translatedText.slice(cursor, span.offset)}</span>);
      }

      const markStyleKey = span.status === "accepted" ? "accepted"
        : span.status === "dismissed" ? "dismissed"
        : span.risk_level;
      const style = RISK_MARK_STYLES[markStyleKey] || RISK_MARK_STYLES.medium;
      const isHighlighted = highlightedIndex === span.index;
      const borderStyle = span.status === "dismissed" ? "3px dashed" : "3px solid";

      parts.push(
        <RiskAnnotationPopover key={`m-${span.index}`} annotation={span}>
          <mark
            ref={(el) => { if (el) markRefs.current.set(span.index, el); }}
            className="cursor-pointer rounded-sm pr-1 pl-1.5 transition-colors duration-150"
            style={{
              borderLeft: `${borderStyle} ${style.border}`,
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

    if (cursor < result.translatedText.length) {
      parts.push(<span key={`t-${cursor}`}>{result.translatedText.slice(cursor)}</span>);
    }

    return parts;
  }, [result, spans, highlightedIndex, handleMarkHover, handleMarkLeave]);

  // Render placeholder states
  if (!result) {
    return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">请在左侧选择目标语言并开始转译</div>;
  }
  if (result.status === "idle") {
    return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">等待转译...</div>;
  }
  if (result.status === "failed") {
    return <div className="flex h-full items-center justify-center text-sm text-danger">转译失败，请重试</div>;
  }

  return (
    <div className="h-full overflow-y-auto rounded-md border border-border bg-white p-3 text-sm leading-relaxed text-foreground">
      <CulturalAdaptationPanel language={language} />
      <div className="whitespace-pre-wrap" dir="auto">{content}</div>
    </div>
  );
}
