"use client";

import { useState } from "react";

interface TranslationDecisionBadgeProps {
  index: number;
  term: string;
  rendering: string;
  notes?: string;
  riskNotes?: string;
}

export function TranslationDecisionBadge({
  index,
  term,
  rendering,
  notes,
  riskNotes,
}: TranslationDecisionBadgeProps) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-block">
      <sup
        className="ml-0.5 cursor-pointer rounded-full bg-teal px-1 text-[10px] font-bold text-white hover:bg-teal-light"
        onClick={() => setOpen(!open)}
      >
        {index}
      </sup>
      {open && (
        <div className="absolute bottom-full left-1/2 z-50 mb-1 w-56 -translate-x-1/2 rounded-md border border-border bg-white p-3 shadow-lg">
          <div className="text-xs font-semibold">术语决策 #{index}</div>
          <div className="mt-1 text-xs text-muted-foreground">原文：「{term}」</div>
          <div className="mt-1 text-xs text-teal-700">选用译法：{rendering}</div>
          {notes && (
            <div className="mt-1 text-xs text-muted-foreground">备注：{notes}</div>
          )}
          {riskNotes && (
            <div className="mt-1 text-xs text-orange-600">⚠ {riskNotes}</div>
          )}
          <div className="mt-1 text-[10px] text-muted-foreground">来源：系统知识库</div>
          <button
            className="absolute right-1 top-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setOpen(false)}
          >×</button>
        </div>
      )}
    </span>
  );
}
