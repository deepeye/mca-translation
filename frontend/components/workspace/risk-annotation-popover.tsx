"use client";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { RiskSpan } from "@/stores/translation-store";

const RISK_STYLES: Record<string, { label: string; badgeBg: string; badgeText: string }> = {
  high: { label: "高风险", badgeBg: "#FEE2E2", badgeText: "#DC2626" },
  medium: { label: "中风险", badgeBg: "#FFEDD5", badgeText: "#C2410C" },
  low: { label: "低风险", badgeBg: "#FEF9C3", badgeText: "#A16207" },
};

const RISK_TYPE_LABELS: Record<string, string> = {
  cognitive_bias: "认知偏差",
  negative_association: "负面联想",
  ambiguity: "歧义",
};

interface RiskAnnotationPopoverProps {
  annotation: RiskSpan;
  children: React.ReactNode;
}

export function RiskAnnotationPopover({ annotation, children }: RiskAnnotationPopoverProps) {
  const style = RISK_STYLES[annotation.risk_level] || RISK_STYLES.medium;

  return (
    <Popover>
      <PopoverTrigger render={children as React.ReactElement} openOnHover delay={150} closeDelay={150} />
      <PopoverContent side="bottom" align="start" sideOffset={6} className="w-72 p-3">
        <div className="flex items-center gap-1.5 mb-1.5">
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
            style={{ background: style.badgeBg, color: style.badgeText }}
          >
            {style.label}
          </span>
          <span className="inline-flex items-center rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[10px] text-[#475569]">
            {RISK_TYPE_LABELS[annotation.risk_type] ?? annotation.risk_type}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-[#334155] line-clamp-3">
          {annotation.explanation}
        </p>
      </PopoverContent>
    </Popover>
  );
}
