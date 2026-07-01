// frontend/components/workspace/decision-log-panel.tsx
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslationStore } from "@/stores/translation-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import type { DecisionLogEntry } from "@/lib/api-client";
import { DecisionLogSkeleton } from "./decision-log-skeleton";
import { DecisionStageGroup } from "./decision-stage-group";

const STAGE_ORDER = ["preprocess", "glossary", "translate", "risk", "suggestion"];

export function DecisionLogPanel() {
  const languages = useWorkspaceStore((s) => s.languages);
  const jobId = useWorkspaceStore((s) => s.currentJobId);
  const [activeLang, setActiveLang] = useState(languages[0] || "en-GB");
  const results = useTranslationStore((s) => s.results);
  const decisionLogs = useTranslationStore((s) => s.decisionLogs);
  const isLoading = useTranslationStore((s) => s.isLoadingDecisions);
  const loadDecisionLogs = useTranslationStore((s) => s.loadDecisionLogs);
  const clearDecisionLogs = useTranslationStore((s) => s.clearDecisionLogs);
  const [collapsed, setCollapsed] = useState(true);
  const entryRefs = useRef<Map<string, HTMLElement | null>>(new Map());

  // Sync active lang with workspace languages
  if (!languages.includes(activeLang) && languages.length > 0) {
    setActiveLang(languages[0]);
  }

  const currentResult = results[activeLang];
  // 假设 result 对象上有 resultId（由 WS / loadFromHistory 填充）
  const resultId = (currentResult as { resultId?: string } | undefined)?.resultId ?? null;

  useEffect(() => {
    if (resultId && !collapsed) {
      loadDecisionLogs(resultId);
    } else if (!resultId) {
      clearDecisionLogs();
    }
  }, [resultId, collapsed, loadDecisionLogs, clearDecisionLogs]);

  // 按 stage 分组
  const grouped = useMemo(() => {
    const map: Record<string, DecisionLogEntry[]> = {};
    for (const log of decisionLogs) {
      (map[log.stage] ??= []).push(log);
    }
    return map;
  }, [decisionLogs]);

  return (
    <div className="border rounded-lg bg-card">
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="flex items-center gap-2 w-full text-left px-3 py-2 hover:bg-muted/50 rounded-t-lg"
      >
        <span className="text-xs">{collapsed ? "▸" : "▾"}</span>
        <span className="text-sm font-semibold">决策日志</span>
        {!collapsed && decisionLogs.length > 0 && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
            {decisionLogs.length}
          </span>
        )}
      </button>
      {!collapsed && (
        <div className="px-3 pb-3 space-y-3 max-h-96 overflow-y-auto">
          {isLoading ? (
            <DecisionLogSkeleton />
          ) : decisionLogs.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center">
              本次翻译无关键决策记录
            </p>
          ) : (
            STAGE_ORDER.filter((s) => grouped[s]).map((stage) => (
              <DecisionStageGroup
                key={stage}
                stage={stage}
                entries={grouped[stage]}
                registerEntryRef={(entry) => (el) => {
                  entryRefs.current.set(entry.id, el);
                }}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
