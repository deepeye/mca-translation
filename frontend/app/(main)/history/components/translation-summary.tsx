"use client";

import { useState } from "react";
import type { CulturalAdaptation, RiskAnnotation } from "@/stores/translation-store";

export interface TranslationResultData {
  id: string;                // 译文结果 ID，用于拉取决策日志
  language: string;
  status: string;
  translated_text: string | null;
  risk_annotations: RiskAnnotation[] | null;
  acceptance_score: number;
  cultural_adaptation: CulturalAdaptation | null;
}

interface TranslationSummaryProps {
  results: TranslationResultData[];
}

const STATUS_ICONS: Record<string, string> = {
  completed: "✓",
  failed: "✗",
  streaming: "⟳",
  idle: "○",
};

export function TranslationSummary({ results }: TranslationSummaryProps) {
  const [expandedLang, setExpandedLang] = useState<string | null>(null);
  const [allExpanded, setAllExpanded] = useState(false);

  if (results.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">暂无翻译结果</p>
    );
  }

  const toggleAll = () => {
    setAllExpanded(!allExpanded);
    setExpandedLang(null);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm">🌐</span>
        {results.length > 1 && (
          <button
            onClick={toggleAll}
            className="text-xs text-teal hover:text-teal-light cursor-pointer"
          >
            {allExpanded ? "全部收起 ▲" : "全部展开 ▼"}
          </button>
        )}
      </div>
      {results.map((r) => {
        const isExpanded = allExpanded || expandedLang === r.language;
        const icon = STATUS_ICONS[r.status] || "?";
        const riskCount = r.risk_annotations?.length || 0;
        const excerpt = r.translated_text
          ? r.translated_text.length > 120
            ? r.translated_text.slice(0, 120) + "..."
            : r.translated_text
          : "";

        return (
          <div key={r.language} className="rounded-lg border border-border">
            <button
              onClick={() => {
                setExpandedLang(isExpanded ? null : r.language);
                setAllExpanded(false);
              }}
              className="flex w-full cursor-pointer items-center justify-between px-3 py-2 text-left text-xs hover:bg-muted/50"
            >
              <div className="flex items-center gap-2">
                <span>{icon}</span>
                <span className="font-medium">{r.language}</span>
                <span className="text-muted-foreground">
                  {r.status === "completed" ? "已完成" : r.status}
                </span>
                {riskCount > 0 && (
                  <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-700">
                    风险 {riskCount} 项
                  </span>
                )}
                {r.acceptance_score >= 0 && (
                  <span className="text-muted-foreground">评分 {r.acceptance_score}</span>
                )}
              </div>
              <span className="text-muted-foreground">{isExpanded ? "▲" : "▼"}</span>
            </button>
            {isExpanded && excerpt && (
              <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
                {excerpt}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
