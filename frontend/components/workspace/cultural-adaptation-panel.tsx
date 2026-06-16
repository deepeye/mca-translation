"use client";

import { useState } from "react";
import { useTranslationStore, type AdaptationStrategy } from "@/stores/translation-store";

const STRATEGY_LABELS: Record<AdaptationStrategy, string> = {
  literal: "直译",
  explanatory: "解释型翻译",
  analogical: "类比翻译",
  reconstruction: "场景重构",
};

const GAP_LABELS: Record<"low" | "medium" | "high", string> = {
  low: "差异度: 低",
  medium: "差异度: 中",
  high: "差异度: 高",
};

const GAP_COLORS: Record<"low" | "medium" | "high", string> = {
  low: "bg-muted text-muted-foreground",
  medium: "bg-orange-100 text-orange-700",
  high: "bg-red-100 text-red-700",
};

export function CulturalAdaptationPanel({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);
  const [open, setOpen] = useState(false);

  const adaptation = result?.culturalAdaptation;
  if (!adaptation) return null;

  const totalTerms = adaptation.culture_loaded_terms.length;
  const hasNotes = adaptation.cultural_notes.length > 0;
  const hasTaboos = adaptation.taboo_warnings.length > 0;
  if (totalTerms === 0 && !hasNotes && !hasTaboos) return null;

  return (
    <div className="mb-2 rounded-md border border-border bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full cursor-pointer items-center justify-between px-3 py-2 text-xs text-foreground hover:bg-muted"
      >
        <span>
          ▾ 文化适配说明
          <span className="ml-2 text-muted-foreground">
            （识别 {totalTerms} 个文化负载词
            {hasNotes ? `、${adaptation.cultural_notes.length} 条注意事项` : ""}
            {hasTaboos ? `、${adaptation.taboo_warnings.length} 条禁忌` : ""}）
          </span>
        </span>
        <span className="text-muted-foreground">{open ? "收起" : "展开"}</span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-border px-3 py-3 text-xs leading-relaxed">
          {totalTerms > 0 && (
            <div className="space-y-2">
              {adaptation.culture_loaded_terms.map((t, i) => (
                <div key={i} className="rounded border border-border/60 bg-muted/30 p-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium text-foreground">{t.term}</span>
                    <span className="rounded bg-teal-lightest px-1.5 py-0.5 text-[11px] text-teal">
                      {STRATEGY_LABELS[t.adaptation_strategy]}
                    </span>
                    <span className={`rounded px-1.5 py-0.5 text-[11px] ${GAP_COLORS[t.culture_gap]}`}>
                      {GAP_LABELS[t.culture_gap]}
                    </span>
                  </div>
                  <div className="mt-1 text-muted-foreground">
                    译法：<span className="text-foreground">{t.suggested_rendering}</span>
                  </div>
                  <div className="text-muted-foreground">原因：{t.reason}</div>
                </div>
              ))}
            </div>
          )}
          {hasNotes && (
            <div>
              <div className="mb-1 text-muted-foreground">⚠️ 文化注意事项</div>
              <ul className="list-disc space-y-0.5 pl-5">
                {adaptation.cultural_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}
          {hasTaboos && (
            <div>
              <div className="mb-1 text-danger">🚫 禁忌提醒</div>
              <ul className="list-disc space-y-0.5 pl-5 text-danger">
                {adaptation.taboo_warnings.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
