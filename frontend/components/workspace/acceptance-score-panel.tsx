"use client";

import { useEffect, useState } from "react";
import { useTranslationStore } from "@/stores/translation-store";
import { AcceptanceDimensionBar } from "./acceptance-dimension-bar";
import { AcceptanceScoreSkeleton } from "./acceptance-score-skeleton";
import { Button } from "@/components/ui/button";
import type { AudienceBaseline } from "@/lib/api-client";

const TEAL = "#0D9488";
const TERRACOTTA = "#C2410C";

const AUDIENCES: { key: AudienceBaseline; label: string }[] = [
  { key: "policy_media", label: "主流媒体" },
  { key: "academic", label: "学术界" },
  { key: "social_media", label: "社交媒体" },
];

const RISK_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };

export function AcceptanceScorePanel({ language }: { language: string }) {
  const activeLang = language;

  const result = useTranslationStore((s) => s.results[activeLang]);
  const triggerFirstScoring = useTranslationStore((s) => s.triggerFirstScoring);
  const setResult = useTranslationStore((s) => s.setResult);
  const clearAcceptanceScore = useTranslationStore((s) => s.clearAcceptanceScore);

  // 折叠状态 — 默认展开（评分是首要反馈，转译完成即可见；区别于 DecisionLogPanel 默认折叠）
  const [collapsed, setCollapsed] = useState(false);

  // 转译完成后自动首次评分（幂等：仅 completed + acceptanceScore===-1 + 未在评分中 + 未尝试过）
  useEffect(() => {
    if (result?.status === "completed" && result.acceptanceScore === -1 && !result.isScoringAcceptance && !result.firstScoringAttempted) {
      triggerFirstScoring(activeLang, result.audienceBaseline || "policy_media");
    }
  }, [result?.status, result?.acceptanceScore, result?.isScoringAcceptance, result?.firstScoringAttempted, activeLang, triggerFirstScoring]);

  // 切换语言时清空（新 lang 的评分由其自身 effect 触发）
  useEffect(() => {
    if (result?.status !== "completed") {
      clearAcceptanceScore(activeLang);
    }
  }, [activeLang, result?.status, clearAcceptanceScore]);

  if (!result || result.status !== "completed" || !result.translatedText) {
    return null;
  }

  const scoring = !!result.isScoringAcceptance;
  const score = result.acceptanceScore;
  const dims = result.acceptanceDimensions;
  const confidence = result.acceptanceConfidence ?? 1;
  const top3 = result.acceptanceTop3Risks ?? [];
  const baseline = result.audienceBaseline || "policy_media";
  const annotations = result.riskAnnotations ?? [];

  const lowConf = confidence < 0.7;
  const veryLowConf = confidence < 0.3;

  const handleTop3Click = (index: number) => {
    setResult(activeLang, { highlightedIndex: index });
    window.dispatchEvent(new CustomEvent("scroll-to-risk-mark", { detail: { language: activeLang, index } }));
  };

  const handleAudienceSwitch = (ab: AudienceBaseline) => {
    if (scoring || ab === baseline) return;
    void triggerFirstScoring(activeLang, ab)
      .then((ok) => { if (!ok) alert("受众基准切换失败"); });
  };

  return (
    <div className="border rounded-lg bg-card">
      <div className="flex items-center justify-between px-3 py-2">
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="flex items-center gap-2 text-left hover:bg-muted/50 rounded"
        >
          <span className="text-xs">{collapsed ? "▸" : "▾"}</span>
          <span className="text-sm font-semibold" style={{ color: TEAL }}>接受度评分</span>
        </button>
        <div className="flex items-center gap-1">
          {AUDIENCES.map((a) => (
            <Button
              key={a.key}
              variant="outline"
              size="sm"
              disabled={scoring}
              onClick={() => handleAudienceSwitch(a.key)}
              className={`h-6 px-2 text-xs ${a.key === baseline ? "bg-teal text-white border-teal" : ""}`}
            >
              {a.label}
            </Button>
          ))}
        </div>
      </div>

      {!collapsed && (scoring ? (
        <AcceptanceScoreSkeleton />
      ) : score === -1 ? (
        <div className="px-3 pb-3 text-center">
          <p className="text-xs text-muted-foreground py-2">接受度评分暂不可用</p>
          <Button variant="outline" size="sm" onClick={() => triggerFirstScoring(activeLang, baseline)}>重试</Button>
        </div>
      ) : (
        <div className="px-3 pb-3 space-y-2">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold" style={{ color: lowConf ? "#9CA3AF" : TEAL }}>{score}</span>
            <span className="text-xs text-muted-foreground">/ 100</span>
            {veryLowConf && <span className="text-xs" style={{ color: TERRACOTTA }}>评分置信度低，仅供参考</span>}
            {lowConf && !veryLowConf && <span className="text-xs" style={{ color: TERRACOTTA }}>评分置信度较低</span>}
          </div>

          {dims && (
            <div className="space-y-1">
              <AcceptanceDimensionBar label="受众匹配度" score={dims.audience} />
              <AcceptanceDimensionBar label="文化敏感度" score={dims.cultural} />
              <AcceptanceDimensionBar label="表达自然度" score={dims.naturalness} />
              <AcceptanceDimensionBar label="风险词密度" score={dims.risk} />
            </div>
          )}

          {top3.length > 0 && (
            <div className="pt-1">
              <p className="text-xs text-muted-foreground mb-1">Top 风险</p>
              <div className="space-y-1">
                {top3.map((idx) => {
                  const ann = annotations[idx];
                  if (!ann) return null;
                  return (
                    <button
                      key={idx}
                      onClick={() => handleTop3Click(idx)}
                      className="flex items-center gap-2 w-full text-left text-xs px-2 py-1 rounded hover:bg-muted/50"
                    >
                      <span className="px-1.5 py-0.5 rounded text-white" style={{ background: `var(--color-risk-${ann.risk_level})` }}>
                        {RISK_LABEL[ann.risk_level] || ann.risk_level}
                      </span>
                      <span className="truncate">{ann.phrase}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <p className="text-[10px] text-muted-foreground pt-1">
            基于 LLM 的接受度估计（受众基准：{AUDIENCES.find((a) => a.key === baseline)?.label}），非审计级，仅供参考
          </p>
        </div>
      ))}
    </div>
  );
}
