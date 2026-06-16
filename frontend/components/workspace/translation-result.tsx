"use client";

import { useMemo, useRef, useCallback, useEffect } from "react";
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

    if (cursor < result.translatedText.length) {
      parts.push(<span key={`t-${cursor}`}>{result.translatedText.slice(cursor)}</span>);
    }

    return parts;
  }, [result.translatedText, result.status, spans, highlightedIndex, handleMarkHover, handleMarkLeave]);

  return (
    <div className="h-full overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-white p-3 text-sm leading-relaxed text-foreground">
      {content}
    </div>
  );
}
