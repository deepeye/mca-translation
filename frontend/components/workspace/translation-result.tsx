"use client";

import { useTranslationStore } from "@/stores/translation-store";

export function TranslationResult({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);

  if (!result) {
    return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">请在左侧选择目标语言并开始转译</div>;
  }
  if (result.status === "idle") {
    return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">等待转译...</div>;
  }
  if (result.status === "failed") {
    return <div className="flex h-full items-center justify-center text-sm text-danger">转译失败，请重试</div>;
  }

  return (
    <div className="h-full overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-white p-3 text-sm leading-relaxed text-foreground">
      {result.translatedText || "正在生成..."}
    </div>
  );
}
