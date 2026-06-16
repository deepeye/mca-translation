"use client";

import { Strategy, useWorkspaceStore } from "@/stores/workspace-store";

const STRATEGIES: { value: Strategy; label: string }[] = [
  { value: "semantic_equivalence", label: "信息等值" },
  { value: "audience_first", label: "受众优先" },
  { value: "literal_reference", label: "直译参考" },
];

export function StrategySelector() {
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const setStrategy = useWorkspaceStore((s) => s.setStrategy);

  return (
    <div className="flex gap-3 text-xs text-muted-foreground">
      {STRATEGIES.map((s) => (
        <label key={s.value} className="flex cursor-pointer items-center gap-1.5">
          <span
            className={`inline-block h-3.5 w-3.5 rounded-full border-2 ${
              strategy === s.value ? "border-teal bg-teal" : "border-muted-foreground/30"
            }`}
            onClick={() => setStrategy(s.value)}
          />
          <span>{s.label}</span>
        </label>
      ))}
    </div>
  );
}
