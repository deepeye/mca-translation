// frontend/components/workspace/decision-stage-group.tsx
"use client";

import { useState } from "react";
import type { DecisionLogEntry } from "@/lib/api-client";
import { DecisionLogEntryItem } from "./decision-log-entry";

const STAGE_LABELS: Record<string, string> = {
  preprocess: "文化预处理",
  glossary: "术语检索",
  translate: "翻译约束",
  risk: "风险标注",
  suggestion: "替换建议",
};

export function DecisionStageGroup({
  stage,
  entries,
  registerEntryRef,
}: {
  stage: string;
  entries: DecisionLogEntry[];
  registerEntryRef?: (entry: DecisionLogEntry) => (el: HTMLElement | null) => void;
}) {
  const [open, setOpen] = useState(true);
  const label = STAGE_LABELS[stage] ?? stage;

  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 w-full text-left hover:bg-muted/50 rounded px-1 py-0.5"
      >
        <span className="text-xs">{open ? "▾" : "▸"}</span>
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
          {entries.length}
        </span>
      </button>
      {open && (
        <div className="space-y-2 pl-4">
          {entries.map((entry) => (
            <DecisionLogEntryItem
              key={entry.id}
              entry={entry}
              registerRef={registerEntryRef?.(entry)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
