"use client";

import { useEffect, useRef } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useGlossaryStore } from "@/stores/glossary-store";
import { apiClient } from "@/lib/api-client";
import { InlineHighlighter } from "./inline-highlighter";
import { TermHighlighter } from "./term-highlighter";

export function TextEditor() {
  const text = useWorkspaceStore((s) => s.input.text);
  const culturalSphere = useWorkspaceStore((s) => s.input.culturalSphere);
  const audienceType = useWorkspaceStore((s) => s.input.audienceType);
  const genre = useWorkspaceStore((s) => s.input.genre);

  const culturalTerms = useGlossaryStore((s) => s.culturalTerms);
  const detectedTerms = useGlossaryStore((s) => s.detectedTerms);
  const culturalAnalysisState = useGlossaryStore((s) => s.culturalAnalysisState);
  const setDetectedTerms = useGlossaryStore((s) => s.setDetectedTerms);
  const setCulturalTerms = useGlossaryStore((s) => s.setCulturalTerms);
  const setCulturalAnalysisState = useGlossaryStore(
    (s) => s.setCulturalAnalysisState,
  );
  const clearHighlights = useGlossaryStore((s) => s.clearHighlights);

  // 文本变更后，若已分析则置 stale（提示用户重新分析）。
  // 用 ref 读取最新状态，避免把 state 放入 deps 导致刚 analyzed 即被置 stale。
  const stateRef = useRef(culturalAnalysisState);
  stateRef.current = culturalAnalysisState;
  useEffect(() => {
    if (stateRef.current === "analyzed") setCulturalAnalysisState("stale");
  }, [text, setCulturalAnalysisState]);

  // 串行调用术语库检测与文化负载词检测，任一接口失败独立降级。
  const analyze = async () => {
    setCulturalAnalysisState("loading");

    let glossaryTerms: typeof detectedTerms = [];
    let culturalTermsResult: typeof culturalTerms = [];
    let glossarySuccess = false;
    let culturalSuccess = false;

    try {
      const result = await apiClient.detectTerms(text);
      glossaryTerms = result.terms || [];
      glossarySuccess = true;
    } catch {
      glossaryTerms = [];
    }

    try {
      const result = await apiClient.detectCulturalTerms({
        text,
        cultural_sphere: culturalSphere,
        audience_type: audienceType,
        genre,
      });
      culturalTermsResult = result.terms || [];
      culturalSuccess = true;
    } catch {
      culturalTermsResult = [];
    }

    setDetectedTerms(glossaryTerms);
    setCulturalTerms(culturalTermsResult);
    setCulturalAnalysisState(glossarySuccess || culturalSuccess ? "analyzed" : "idle");
  };

  const tooLong = text.length > 5000;
  const buttonDisabled =
    !text.trim() || tooLong || culturalAnalysisState === "loading";

  // 清除高亮：仅在 analyzed/stale 且有结果时可用；loading 或无结果时禁用
  const clearDisabled =
    culturalAnalysisState === "loading" ||
    culturalAnalysisState === "idle" ||
    (detectedTerms.length + culturalTerms.length === 0);

  const buttonLabel = (() => {
    switch (culturalAnalysisState) {
      case "loading":
        return "识别中…";
      case "analyzed":
        return `已分析 ${detectedTerms.length + culturalTerms.length} 个术语与文化负载词`;
      case "stale":
        return "原文已变更，重新分析";
      default:
        return "分析术语与文化负载词";
    }
  })();

  return (
    <div className="relative flex flex-1 flex-col gap-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={analyze}
          disabled={buttonDisabled}
          title={
            tooLong ? "原文过长（>5000 字），建议分段" : "识别术语与文化负载词并高亮"
          }
          className="rounded-md border border-border bg-white px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          {buttonLabel}
        </button>
        <button
          type="button"
          onClick={clearHighlights}
          disabled={clearDisabled}
          title="清除已识别的术语与文化负载词高亮"
          className="rounded-md border border-border bg-white px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          清除高亮
        </button>
      </div>

      <div className="flex-1">
        <InlineHighlighter />
      </div>

      <TermHighlighter containerClassName="px-1" />

      <div className="absolute bottom-2 right-3 text-xs text-muted-foreground">
        {text.length} / 10000
      </div>
    </div>
  );
}
