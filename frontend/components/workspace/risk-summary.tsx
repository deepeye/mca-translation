"use client";

import { useTranslationStore } from "@/stores/translation-store";

export function RiskSummary({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);
  if (!result?.riskAnnotations?.length) return null;

  const counts = { high: 0, medium: 0, low: 0 };
  for (const a of result.riskAnnotations) {
    counts[a.risk_level] = (counts[a.risk_level] || 0) + 1;
  }

  return (
    <div className="rounded border-l-3 border-terracotta bg-amber-50 px-3 py-2 text-xs text-amber-800">
      <span className="font-medium">风险标注：</span>
      {result.riskAnnotations.length} 处表达在目标受众中存在认知风险
      {counts.high > 0 && <span className="ml-2 text-danger">{counts.high} 高风险</span>}
      {counts.medium > 0 && <span className="ml-2 text-terracotta">{counts.medium} 中风险</span>}
      {counts.low > 0 && <span className="ml-2 text-amber-600">{counts.low} 低风险</span>}
    </div>
  );
}
