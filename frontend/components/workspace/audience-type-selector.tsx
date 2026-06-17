"use client";

import { AudienceType, useWorkspaceStore } from "@/stores/workspace-store";
import { isLiteralMode } from "@/lib/translation-conflicts";

const AUDIENCES: { value: AudienceType; label: string; tip: string }[] = [
  { value: "general_public", label: "公众", tip: "简明、故事化、避免术语" },
  { value: "media", label: "媒体", tip: "客观、可引用、Reuters 风格" },
  { value: "government", label: "政府", tip: "正式、精准、政策语言" },
  { value: "academic", label: "学术", tip: "概念完整、引用规范" },
  { value: "business", label: "企业", tip: "数据驱动、商业语言" },
  { value: "diaspora_chinese", label: "海外华人", tip: "文化共鸣 + 当地语境" },
];

export function AudienceTypeSelector() {
  const audience = useWorkspaceStore((s) => s.input.audienceType);
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const setAudience = useWorkspaceStore((s) => s.setAudienceType);
  const literalMode = isLiteralMode(strategy);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="shrink-0 text-xs text-muted-foreground">受众</span>
      <div className={`flex flex-wrap items-center gap-1.5 ${literalMode ? "opacity-50 pointer-events-none" : ""}`}>
        {AUDIENCES.map((a) => (
          <button
            key={a.value}
            onClick={() => setAudience(a.value)}
            title={a.tip}
            className={`cursor-pointer rounded-full px-2.5 py-1 text-xs transition-all duration-200 active:scale-[0.95] ${
              audience === a.value
                ? "bg-teal text-white"
                : "bg-muted text-muted-foreground hover:bg-teal-lightest"
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>
      {literalMode && (
        <span className="text-[11px] text-muted-foreground">直译参考模式下不进行文化适配</span>
      )}
    </div>
  );
}
