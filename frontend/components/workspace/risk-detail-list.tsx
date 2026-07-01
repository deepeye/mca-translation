"use client";

import { useState, useCallback } from "react";
import { useTranslationStore, type RiskAnnotation } from "@/stores/translation-store";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Loader2, X, RotateCcw, ChevronDown, ChevronRight, Sparkles } from "lucide-react";

const RISK_BADGE_STYLES: Record<string, { label: string; badgeBg: string; badgeText: string; borderColor: string }> = {
  high: { label: "高风险", badgeBg: "var(--color-risk-high-bg)", badgeText: "var(--color-risk-high-text)", borderColor: "var(--color-risk-high-border)" },
  medium: { label: "中风险", badgeBg: "var(--color-risk-medium-bg)", badgeText: "var(--color-risk-medium-text)", borderColor: "var(--color-risk-medium-border)" },
  low: { label: "低风险", badgeBg: "var(--color-risk-low-bg)", badgeText: "var(--color-risk-low-text)", borderColor: "var(--color-risk-low-border)" },
};

const RISK_TYPE_LABELS: Record<string, string> = {
  cognitive_bias: "认知偏差",
  negative_association: "负面联想",
  ambiguity: "歧义",
};

const STATUS_STYLES: Record<string, { borderColor: string; bg: string }> = {
  open: { borderColor: "var(--color-border)", bg: "white" },
  accepted: { borderColor: "var(--color-risk-accepted-border)", bg: "var(--color-risk-accepted-bg)" },
  dismissed: { borderColor: "var(--color-risk-dismissed-border)", bg: "var(--color-risk-dismissed-bg)" },
};

interface Suggestion {
  text: string;
  reason: string;
}

function mapAnnotations(raw: Record<string, unknown>[]): RiskAnnotation[] {
  return raw.map((a) => ({
    phrase: (a.phrase || a.span_text) as string,
    risk_level: a.risk_level as "low" | "medium" | "high",
    risk_type: a.risk_type as string,
    explanation: a.explanation as string,
    status: (a.status as "open" | "accepted" | "dismissed") || "open",
    accepted_suggestion: a.accepted_suggestion as string | undefined,
    offset: a.offset as number | undefined,
  }));
}

function RiskDetailCard({
  annotation,
  index,
  language,
  jobId,
  isHighlighted,
  onHover,
  onLeave,
  onClick,
}: {
  annotation: RiskAnnotation;
  index: number;
  language: string;
  jobId: string | null;
  isHighlighted: boolean;
  onHover: (index: number) => void;
  onLeave: () => void;
  onClick: (index: number) => void;
}) {
  const riskStyle = RISK_BADGE_STYLES[annotation.risk_level] || RISK_BADGE_STYLES.medium;
  const statusStyle = STATUS_STYLES[annotation.status || "open"];
  const status = annotation.status || "open";

  const [suggestions, setSuggestions] = useState<Suggestion[] | null>(null);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [suggestionError, setSuggestionError] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [collapsed, setCollapsed] = useState(status === "dismissed");

  const acceptRisk = useTranslationStore((s) => s.acceptRisk);
  const dismissRisk = useTranslationStore((s) => s.dismissRisk);
  const revertRisk = useTranslationStore((s) => s.revertRisk);

  const handleViewSuggestions = useCallback(async () => {
    if (!jobId) return;
    setLoadingSuggestions(true);
    setSuggestionError(false);
    try {
      const data = await apiClient.get(`/api/jobs/${jobId}/suggestions?lang=${language}&risk_index=${index}`);
      setSuggestions(data.suggestions || []);
    } catch {
      setSuggestionError(true);
    } finally {
      setLoadingSuggestions(false);
    }
  }, [jobId, language, index]);

  const handleAccept = useCallback(async (suggestion: string) => {
    if (!jobId) return;
    setActionLoading(true);
    try {
      const data = await apiClient.post(`/api/jobs/${jobId}/risks/${index}/accept`, { suggestion, lang: language });
      const result = data.results?.find((r: { language: string }) => r.language === language);
      if (result) {
        acceptRisk(language, index, suggestion, result.translated_text, mapAnnotations(result.risk_annotations || []));
        setSuggestions(null);
        // 接受替换后触发接受度评分 delta 重算（失败保留旧分，不阻塞）
        void useTranslationStore.getState().triggerDeltaScoring(language, index);
      }
    } finally {
      setActionLoading(false);
    }
  }, [jobId, language, index, acceptRisk]);
  const handleDismiss = useCallback(async () => {
    if (!jobId) return;
    setActionLoading(true);
    try {
      const data = await apiClient.post(`/api/jobs/${jobId}/risks/${index}/dismiss`, { lang: language });
      const result = data.results?.find((r: { language: string }) => r.language === language);
      if (result) {
        dismissRisk(language, index, mapAnnotations(result.risk_annotations || []));
      }
    } finally {
      setActionLoading(false);
    }
  }, [jobId, language, index, dismissRisk]);

  const handleRevert = useCallback(async () => {
    if (!jobId) return;
    setActionLoading(true);
    try {
      const data = await apiClient.post(`/api/jobs/${jobId}/risks/${index}/revert`, { lang: language });
      const result = data.results?.find((r: { language: string }) => r.language === language);
      if (result) {
        revertRisk(language, index, result.translated_text, mapAnnotations(result.risk_annotations || []));
        void useTranslationStore.getState().triggerDeltaScoring(language, index);
      }
    } finally {
      setActionLoading(false);
    }
  }, [jobId, language, index, revertRisk]);

  // Dismissed collapsed view
  if (collapsed && status === "dismissed") {
    return (
      <div
        className="flex items-center gap-2 rounded border border-dashed px-3 py-1.5 text-xs text-muted-foreground cursor-pointer"
        style={{ borderColor: "var(--color-risk-dismissed-border)", background: "var(--color-risk-dismissed-bg)" }}
        onClick={() => setCollapsed(false)}
      >
        <ChevronRight className="h-3 w-3" />
        <span>&ldquo;{annotation.phrase}&rdquo;</span>
        <span>已忽略</span>
      </div>
    );
  }

  return (
    <div
      className="rounded-md border p-2.5 transition-all duration-200 hover:shadow-sm cursor-pointer"
      style={{
        background: statusStyle.bg,
        borderColor: isHighlighted ? riskStyle.borderColor : statusStyle.borderColor,
        ...(status === "dismissed" ? { borderStyle: "dashed" } : {}),
      }}
      onMouseEnter={() => onHover(index)}
      onMouseLeave={onLeave}
      onClick={() => onClick(index)}
    >
      {/* Header row */}
      <div className="flex flex-wrap items-center gap-1.5 mb-1">
        <span
          className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold"
          style={{ background: riskStyle.badgeBg, color: riskStyle.badgeText }}
        >
          {riskStyle.label}
        </span>
        <span className="text-xs font-medium text-teal-dark">&ldquo;{annotation.phrase}&rdquo;</span>
        <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {RISK_TYPE_LABELS[annotation.risk_type] ?? annotation.risk_type}
        </span>

        {/* Status badge + actions */}
        <div className="ml-auto flex items-center gap-1">
          {status === "accepted" && (
            <span className="inline-flex items-center rounded-full bg-risk-accepted/10 px-2 py-0.5 text-[10px] font-medium text-risk-accepted">
              已采纳：{annotation.phrase} → {annotation.accepted_suggestion}
            </span>
          )}
          {status === "dismissed" && (
            <button
              className="rounded p-0.5 text-muted-foreground hover:text-foreground"
              onClick={(e) => { e.stopPropagation(); setCollapsed(true); }}
              title="折叠"
            >
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
          )}
          {status === "open" && !actionLoading && (
            <button
              className="rounded p-0.5 text-muted-foreground hover:text-foreground"
              onClick={(e) => { e.stopPropagation(); handleDismiss(); }}
              title="忽略"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          {actionLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
        </div>
      </div>

      {/* Explanation */}
      <p className={`text-[11px] leading-relaxed ${status === "dismissed" ? "text-muted-foreground" : "text-muted-foreground"}`}>
        {annotation.explanation}
      </p>

      {/* Revert button for accepted */}
      {status === "accepted" && (
        <div className="mt-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] px-2"
            onClick={(e) => { e.stopPropagation(); handleRevert(); }}
            disabled={actionLoading}
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            回退
          </Button>
        </div>
      )}

      {/* Dismissed: undo dismiss */}
      {status === "dismissed" && (
        <div className="mt-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] px-2"
            onClick={(e) => { e.stopPropagation(); handleDismiss(); }}
            disabled={actionLoading}
          >
            撤销忽略
          </Button>
        </div>
      )}

      {/* View suggestions button for open */}
      {status === "open" && suggestions === null && !suggestionError && (
        <div className="mt-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] px-2"
            onClick={(e) => { e.stopPropagation(); handleViewSuggestions(); }}
            disabled={loadingSuggestions}
          >
            {loadingSuggestions ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3 mr-1" />
            )}
            查看替代方案
          </Button>
        </div>
      )}

      {/* Suggestion error */}
      {suggestionError && (
        <div className="mt-1.5 flex items-center gap-2">
          <span className="text-[11px] text-danger">生成建议失败</span>
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] px-2"
            onClick={(e) => { e.stopPropagation(); handleViewSuggestions(); }}
          >
            重试
          </Button>
        </div>
      )}

      {/* Suggestion cards */}
      {suggestions && suggestions.length > 0 && (
        <div className="mt-1.5 flex flex-col gap-1">
          {suggestions.map((s, si) => (
            <div key={si} className="rounded border border-teal/20 bg-teal-lightest/60 p-2">
              <p className="text-[11px] font-medium text-teal-dark">{s.text}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{s.reason}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-1 h-5 text-[10px] px-2"
                onClick={(e) => { e.stopPropagation(); handleAccept(s.text); }}
                disabled={actionLoading}
              >
                采纳
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* No suggestions found */}
      {suggestions && suggestions.length === 0 && (
        <p className="mt-1.5 text-[11px] text-muted-foreground">未找到替代方案</p>
      )}
    </div>
  );
}

export function RiskDetailList({ language, jobId }: { language: string; jobId: string | null }) {
  const result = useTranslationStore((s) => s.results[language]);
  const setResult = useTranslationStore((s) => s.setResult);
  const acceptRisk = useTranslationStore((s) => s.acceptRisk);

  const annotations = result?.riskAnnotations ?? [];
  const highlightedIndex = result?.highlightedIndex ?? null;

  const [acceptAllLoading, setAcceptAllLoading] = useState(false);

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

  const handleAcceptAll = useCallback(async () => {
    if (!jobId) return;
    setAcceptAllLoading(true);
    try {
      const data = await apiClient.post(`/api/jobs/${jobId}/risks/accept-all`, { lang: language });
      const resultData = data.results?.find((r: { language: string }) => r.language === language);
      if (resultData) {
        acceptRisk(language, -1, "", resultData.translated_text, mapAnnotations(resultData.risk_annotations || []));
        // 多句改动 → 全文重算（首次评分端点），非单句 delta
        const ab = useTranslationStore.getState().results[language]?.audienceBaseline || "policy_media";
        void useTranslationStore.getState().triggerFirstScoring(language, ab);
      }
    } catch (err) {
      if (err instanceof Error && err.message.includes("409")) {
        alert("正在批量处理中");
      }
    } finally {
      setAcceptAllLoading(false);
    }
  }, [jobId, language, acceptRisk]);

  if (!annotations.length) return null;

  const openCount = annotations.filter((a) => (a.status || "open") === "open").length;
  const acceptedCount = annotations.filter((a) => a.status === "accepted").length;
  const dismissedCount = annotations.filter((a) => a.status === "dismissed").length;

  return (
    <div className="flex flex-col gap-1.5">
      {/* Summary bar */}
      <div className="flex items-center gap-2 rounded border-l-3 border-terracotta bg-teal-lightest/80 px-3 py-2 text-xs text-teal-dark">
        <span>
          <span className="font-heading font-medium">风险标注：</span>
          {openCount > 0 ? (
            <>
              {annotations.length} 处表达在目标受众中存在认知风险
              {annotations.filter((a) => a.risk_level === "high" && (a.status || "open") === "open").length > 0 && (
                <span className="ml-2 text-danger">{annotations.filter((a) => a.risk_level === "high" && (a.status || "open") === "open").length} 高风险</span>
              )}
              {annotations.filter((a) => a.risk_level === "medium" && (a.status || "open") === "open").length > 0 && (
                <span className="ml-2 text-terracotta">{annotations.filter((a) => a.risk_level === "medium" && (a.status || "open") === "open").length} 中风险</span>
              )}
              {annotations.filter((a) => a.risk_level === "low" && (a.status || "open") === "open").length > 0 && (
                <span className="ml-2 text-risk-low">{annotations.filter((a) => a.risk_level === "low" && (a.status || "open") === "open").length} 低风险</span>
              )}
            </>
          ) : (
            "所有风险已处理"
          )}
          {acceptedCount > 0 && <span className="ml-2 text-risk-accepted">{acceptedCount} 已采纳</span>}
          {dismissedCount > 0 && <span className="ml-2 text-muted-foreground">{dismissedCount} 已忽略</span>}
        </span>

        {/* Accept all button */}
        {openCount >= 2 && (
          <Button
            variant="outline"
            size="sm"
            className="ml-auto h-6 text-[11px] px-2 border-terracotta text-terracotta hover:bg-terracotta hover:text-white"
            onClick={handleAcceptAll}
            disabled={acceptAllLoading}
          >
            {acceptAllLoading ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3 mr-1" />
            )}
            一键采纳全部建议
          </Button>
        )}
      </div>

      {/* Detail cards */}
      <div className="flex flex-col gap-1.5">
        {annotations.map((a, index) => (
          <RiskDetailCard
            key={index}
            annotation={a}
            index={index}
            language={language}
            jobId={jobId}
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
