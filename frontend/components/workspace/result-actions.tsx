"use client";

import { useTranslationStore } from "@/stores/translation-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";

export function ResultActions({ language }: { language: string }) {
  const result = useTranslationStore((s) => s.results[language]);
  const sourceText = useWorkspaceStore((s) => s.input.text);

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

  async function handleExportDocx() {
    if (!result?.translatedText) return;
    try {
      const blob = await apiClient.exportDocx({
        source_text: sourceText,
        translated_text: result.translatedText,
        risk_annotations: (result.riskAnnotations || []).map((a) => ({
          phrase: a.phrase,
          risk_level: a.risk_level,
          risk_type: a.risk_type,
          explanation: a.explanation,
        })),
        language,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const now = new Date();
      const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}${String(now.getSeconds()).padStart(2, "0")}`;
      a.download = `translation_${language}_${ts}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export .docx:", err);
    }
  }

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={handleCopy} disabled={!result?.translatedText}>复制</Button>
      <Button variant="outline" size="sm" onClick={handleExportTxt} disabled={!result?.translatedText}>导出 .txt</Button>
      <Button variant="outline" size="sm" onClick={handleExportDocx} disabled={!result?.translatedText}>导出 .docx</Button>
    </div>
  );
}
