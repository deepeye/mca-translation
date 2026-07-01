"use client";

import { useEffect, useRef } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useGlossaryStore } from "@/stores/glossary-store";
import { apiClient } from "@/lib/api-client";
import { InlineHighlighter } from "./inline-highlighter";
import { TermHighlighter } from "./term-highlighter";

// 输入区 — 内联高亮（术语库实时 + LLM 文化负载词手动识别）+ 下方术语概览
export function TextEditor() {
  const text = useWorkspaceStore((s) => s.input.text);
  const setText = useWorkspaceStore((s) => s.setText);
  const culturalSphere = useWorkspaceStore((s) => s.input.culturalSphere);
  const audienceType = useWorkspaceStore((s) => s.input.audienceType);
  const genre = useWorkspaceStore((s) => s.input.genre);

  const culturalTerms = useGlossaryStore((s) => s.culturalTerms);
  const culturalAnalysisState = useGlossaryStore((s) => s.culturalAnalysisState);
  const setCulturalTerms = useGlossaryStore((s) => s.setCulturalTerms);
  const setCulturalAnalysisState = useGlossaryStore(
    (s) => s.setCulturalAnalysisState,
  );

  // 文本变更后，若已分析则置 stale（提示用户重新分析）。
  // 用 ref 读取最新状态，避免把 state 放入 deps 导致刚 analyzed 即被置 stale。
  const stateRef = useRef(culturalAnalysisState);
  stateRef.current = culturalAnalysisState;
  useEffect(() => {
    if (stateRef.current === "analyzed") setCulturalAnalysisState("stale");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  // 手动触发 LLM 文化负载词识别（隐喻/政治话语）
  const analyze = async () => {
    setCulturalAnalysisState("loading");
    try {
      const { terms } = await apiClient.detectCulturalTerms({
        text,
        cultural_sphere: culturalSphere,
        audience_type: audienceType,
        genre,
      });
      setCulturalTerms(terms);
      setCulturalAnalysisState("analyzed");
    } catch {
      // LLM 失败回退 idle，不阻塞输入
      setCulturalTerms([]);
      setCulturalAnalysisState("idle");
    }
  };

  const tooLong = text.length > 5000;
  const buttonDisabled =
    !text.trim() || tooLong || culturalAnalysisState === "loading";

  const buttonLabel = (() => {
    switch (culturalAnalysisState) {
      case "loading":
        return "识别中…";
      case "analyzed":
        return `已分析 ${culturalTerms.length} 个高语境词`;
      case "stale":
        return "原文已变更，重新分析";
      default:
        return "🔍 分析高语境词";
    }
  })();

  return (
    <div className="relative flex flex-1 flex-col gap-2">
      {/* 工具条：分析按钮 */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={analyze}
          disabled={buttonDisabled}
          title={
            tooLong ? "原文过长（>5000 字），建议分段" : "识别政治话语/文化隐喻并高亮"
          }
          className="rounded-md border border-border bg-white px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          {buttonLabel}
        </button>
      </div>

      {/* 内联高亮编辑区 */}
      <div className="flex-1">
        <InlineHighlighter />
      </div>

      {/* 术语概览（badge 列表，悬停详情）— 保留现有功能 */}
      <TermHighlighter text={text} containerClassName="px-1" />

      <div className="absolute bottom-2 right-3 text-xs text-muted-foreground">
        {text.length} / 10000
      </div>
    </div>
  );
}
