// frontend/components/workspace/decision-log-entry.tsx
"use client";

import type { DecisionLogEntry } from "@/lib/api-client";

const CONFIDENCE_BORDER: Record<string, string> = {
  high: "border-l-[#C8553D]",      // 赤陶色
  medium: "border-l-amber-400",    // 琥珀色
  low: "border-l-gray-300",        // 灰色
};

const CONFIDENCE_LABEL: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export function DecisionLogEntryItem({
  entry,
  registerRef,
}: {
  entry: DecisionLogEntry;
  registerRef?: (el: HTMLElement | null) => void;
}) {
  const borderClass = entry.confidence
    ? CONFIDENCE_BORDER[entry.confidence] ?? "border-l-transparent"
    : "border-l-transparent";

  return (
    <div
      ref={registerRef}
      className={`border-l-2 ${borderClass} pl-3 py-1.5 space-y-1`}
    >
      <div className="flex items-center gap-2 flex-wrap">
        {entry.confidence && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
            {CONFIDENCE_LABEL[entry.confidence]}
          </span>
        )}
        <span className="text-sm font-medium">{entry.decision}</span>
      </div>
      {(entry.source_phrase || entry.target_phrase) && (
        <div className="text-xs flex gap-2 flex-wrap">
          {entry.source_phrase && (
            <span className="text-teal-600 dark:text-teal-400 font-mono">
              {entry.source_phrase}
            </span>
          )}
          {entry.source_phrase && entry.target_phrase && (
            <span className="text-muted-foreground">→</span>
          )}
          {entry.target_phrase && (
            <span className="text-teal-600 dark:text-teal-400 font-mono">
              {entry.target_phrase}
            </span>
          )}
        </div>
      )}
      {entry.reasoning && (
        <p className="text-xs text-muted-foreground leading-relaxed">
          {entry.reasoning}
        </p>
      )}
    </div>
  );
}
