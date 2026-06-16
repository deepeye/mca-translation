"use client";

import { useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useTranslationStore } from "@/stores/translation-store";
import { LanguageTabs } from "./language-tabs";
import { TranslationResult } from "./translation-result";
import { RiskSummary } from "./risk-summary";
import { ResultActions } from "./result-actions";

export function OutputPanel() {
  const languages = useWorkspaceStore((s) => s.languages);
  const [activeLang, setActiveLang] = useState(languages[0] || "en-GB");
  const result = useTranslationStore((s) => s.results[activeLang]);

  // Sync active tab when languages change
  if (!languages.includes(activeLang) && languages.length > 0) {
    setActiveLang(languages[0]);
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <LanguageTabs activeLang={activeLang} onSwitch={setActiveLang} />
      <TranslationResult language={activeLang} />
      <RiskSummary language={activeLang} />
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {result?.status === "completed" && "转译完成"}
          {result?.status === "streaming" && "正在转译..."}
          {result?.status === "idle" && "等待中"}
          {result?.status === "failed" && "转译失败"}
        </span>
        <ResultActions language={activeLang} />
      </div>
    </div>
  );
}
