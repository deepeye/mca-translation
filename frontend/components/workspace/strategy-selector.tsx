"use client";

import { Strategy, useWorkspaceStore } from "@/stores/workspace-store";
import { getDisabledStrategies } from "@/lib/translation-conflicts";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const STRATEGIES: {
  value: Strategy;
  label: string;
  desc: string;
  scenario: string;
}[] = [
  {
    value: "semantic_equivalence",
    label: "信息等值",
    desc: "忠实保留原文语义，准确性优先于可读性",
    scenario: "法律文书、外交文件、学术论文",
  },
  {
    value: "audience_first",
    label: "受众优先",
    desc: "侧重目标受众可读性，必要时重构句式",
    scenario: "宣传材料、营销文案、公共沟通",
  },
  {
    value: "literal_reference",
    label: "直译参考",
    desc: "最小化文化适配，逐句对照原文",
    scenario: "专业翻译辅助、原文逐句核查",
  },
];

export function StrategySelector() {
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const genre = useWorkspaceStore((s) => s.input.genre);
  const setStrategy = useWorkspaceStore((s) => s.setStrategy);
  const disabledStrategies = getDisabledStrategies(genre);

  return (
    <TooltipProvider delay={300}>
      <div className="flex gap-3 text-xs text-muted-foreground">
        {STRATEGIES.map((s) => {
          const disabled = disabledStrategies.includes(s.value);
          return (
            <Tooltip key={s.value}>
              <TooltipTrigger
                render={
                  <label
                    className={`flex items-center gap-1.5 ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                    title={disabled ? "与当前文体（品牌传播）冲突，不可选" : undefined}
                    onClick={() => { if (!disabled) setStrategy(s.value); }}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 rounded-full border-2 transition-all duration-200 ${
                        strategy === s.value
                          ? "border-teal bg-teal"
                          : "border-muted-foreground/30"
                      }`}
                    />
                    <span className="font-heading">{s.label}</span>
                  </label> as React.ReactElement
                }
              />
              <TooltipContent side="bottom" className="w-56 flex-col items-start">
                <p>{s.desc}</p>
                {disabled ? (
                  <p className="text-[11px] text-danger mt-1">与当前文体（品牌传播）冲突，不可选</p>
                ) : (
                  <p className="text-[11px] text-background/60 mt-1">适用：{s.scenario}</p>
                )}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
