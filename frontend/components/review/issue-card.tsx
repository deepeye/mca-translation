"use client";

import { useState } from "react";
import type { ReviewIssue } from "@/stores/review-store";

const SEVERITY_STYLES: Record<string, { icon: string; badgeBg: string; badgeText: string; borderColor: string }> = {
  high: { icon: "🔴", badgeBg: "#FEE2E2", badgeText: "#DC2626", borderColor: "#FCA5A5" },
  medium: { icon: "🟠", badgeBg: "#FFEDD5", badgeText: "#C2410C", borderColor: "#FDBA74" },
  low: { icon: "🟡", badgeBg: "#FEF9C3", badgeText: "#A16207", borderColor: "#FDE68A" },
};

const CATEGORY_LABELS: Record<string, string> = {
  terminology: "术语",
  cultural: "文化",
  clarity: "清晰",
  narrative: "叙事",
};

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  terminology: { bg: "#E0F2FE", text: "#0369A1" },
  cultural: { bg: "#FCE7F3", text: "#BE185D" },
  clarity: { bg: "#ECFCCB", text: "#3F6212" },
  narrative: { bg: "#F3E8FF", text: "#7C3AED" },
};

export function IssueCard({
  issue,
  index,
  isHighlighted,
  onHover,
  onLeave,
  onClick,
}: {
  issue: ReviewIssue;
  index: number;
  isHighlighted: boolean;
  onHover: (index: number) => void;
  onLeave: () => void;
  onClick: (index: number) => void;
}) {
  const severity = SEVERITY_STYLES[issue.severity] || SEVERITY_STYLES.low;
  const category = CATEGORY_LABELS[issue.category] || issue.category;
  const catColor = CATEGORY_COLORS[issue.category] || { bg: "#F1F5F9", text: "#475569" };
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-md border p-2.5 transition-colors duration-150 cursor-pointer"
      style={{
        background: isHighlighted ? severity.badgeBg : "white",
        borderColor: isHighlighted ? severity.borderColor : "#E2E8F0",
      }}
      onMouseEnter={() => onHover(index)}
      onMouseLeave={onLeave}
      onClick={() => onClick(index)}
    >
      <div className="flex flex-wrap items-center gap-1.5 mb-1">
        <span
          className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
          style={{ background: severity.badgeBg, color: severity.badgeText }}
        >
          {severity.icon} {issue.severity === "high" ? "高风险" : issue.severity === "medium" ? "中风险" : "低风险"}
        </span>
        <span
          className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-medium"
          style={{ background: catColor.bg, color: catColor.text }}
        >
          {category}
        </span>
        {issue.source_reference && (
          <span className="text-[10px] text-muted-foreground truncate max-w-[150px]">
            对应：「{issue.source_reference}」
          </span>
        )}
      </div>

      <div className="flex items-start gap-1 text-xs mb-1">
        <span className="font-medium text-slate-700 shrink-0">原文：</span>
        <span className="text-slate-500 line-through">{issue.original}</span>
      </div>
      <div className="flex items-start gap-1 text-xs mb-1">
        <span className="font-medium text-teal-700 shrink-0">建议：</span>
        <span className="text-teal-600">{issue.suggestion}</span>
      </div>

      <button
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        className="text-[10px] text-muted-foreground hover:text-foreground mt-0.5"
      >
        {expanded ? "收起" : "查看说明"}
      </button>

      {expanded && (
        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
          {issue.explanation}
        </p>
      )}
    </div>
  );
}
