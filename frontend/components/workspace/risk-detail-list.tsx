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
      {/* Summary bar */}
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
