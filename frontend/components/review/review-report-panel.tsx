"use client";

import { useState } from "react";
import { useReviewStore } from "@/stores/review-store";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";

export function ReviewReportPanel() {
  const result = useReviewStore((s) => s.result);
  const [collapsed, setCollapsed] = useState(false);

  if (!result) return null;

  const handleExport = () => {
    const lines: string[] = [];
    lines.push(`# 审校报告`);
    lines.push(``);
    lines.push(`**总体评分：** ${result.overall_score}/100`);
    lines.push(`**审校模式：** ${result.mode === "dual" ? "对照审校" : "独立诊断"}`);
    lines.push(`**目标语言：** ${result.target_language}`);
    lines.push(`**受众基准：** ${result.audience_baseline}`);
    lines.push(``);
    lines.push(`## 审校摘要`);
    lines.push(result.summary);
    lines.push(``);
    lines.push(`## 分类评分`);
    for (const cat of result.categories) {
      lines.push(`- ${cat.name}：${cat.score}/100（${cat.issue_count} 处问题）`);
    }
    lines.push(``);
    lines.push(`## 问题详情`);
    let idx = 1;
    for (const cat of result.categories) {
      for (const issue of cat.issues) {
        lines.push(`### 问题 ${idx}`);
        lines.push(`- **分类：** ${cat.name}`);
        lines.push(`- **严重级别：** ${issue.severity === "high" ? "高风险" : issue.severity === "medium" ? "中风险" : "低风险"}`);
        lines.push(`- **原文：** ${issue.original}`);
        lines.push(`- **建议：** ${issue.suggestion}`);
        lines.push(`- **说明：** ${issue.explanation}`);
        if (issue.source_reference) {
          lines.push(`- **对应原文：** ${issue.source_reference}`);
        }
        lines.push(``);
        idx++;
      }
    }

    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `审校报告_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="rounded-md border border-border bg-white">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-medium hover:bg-gray-50"
      >
        <span>审校报告</span>
        {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
      </button>

      {!collapsed && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-3 text-sm leading-relaxed text-foreground">{result.summary}</p>

          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {result.categories.map((cat) => (
              <div key={cat.name} className="rounded border border-border p-2 text-center">
                <div className="text-xs text-muted-foreground">{cat.name}</div>
                <div className="text-lg font-semibold text-foreground">{cat.score}</div>
                <div className="text-[10px] text-muted-foreground">{cat.issue_count} 处问题</div>
              </div>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={handleExport}
          >
            <FileText className="mr-1 h-3.5 w-3.5" />
            导出 Markdown
          </Button>
        </div>
      )}
    </div>
  );
}
