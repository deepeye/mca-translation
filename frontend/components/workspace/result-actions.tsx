"use client";

import { useTranslationStore } from "@/stores/translation-store";
import { Button } from "@/components/ui/button";

export function ResultActions({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);

  function handleCopy() {
    if (result?.translatedText) { navigator.clipboard.writeText(result.translatedText); }
  }

  function handleExportTxt() {
    if (!result?.translatedText) return;
    const blob = new Blob([result.translatedText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `translation_${language}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={handleCopy} disabled={!result?.translatedText}>复制</Button>
      <Button variant="outline" size="sm" onClick={handleExportTxt} disabled={!result?.translatedText}>导出 .txt</Button>
    </div>
  );
}
