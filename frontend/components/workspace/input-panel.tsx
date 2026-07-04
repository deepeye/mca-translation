"use client";

import { GenreSelector } from "./genre-selector";
import { CultureSphereSelector } from "./culture-sphere-selector";
import { AudienceTypeSelector } from "./audience-type-selector";
import { TextEditor } from "./text-editor";
import { StrategySelector } from "./strategy-selector";
import { FileUploadZone } from "./file-upload-zone";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useTranslationStore } from "@/stores/translation-store";
import { useCreditsStore } from "@/stores/credits-store";
import { apiClient } from "@/lib/api-client";
import { wsClient } from "@/lib/ws-client";
import { Button } from "@/components/ui/button";
import { isLiteralMode } from "@/lib/translation-conflicts";
import { LANGUAGES } from "@/lib/languages";

export function InputPanel() {
  const store = useWorkspaceStore();
  const setResult = useTranslationStore((s) => s.setResult);
  const resetAll = useTranslationStore((s) => s.resetAll);
  const balance = useCreditsStore((s) => s.balance);
  const insufficient = balance !== null && balance <= 0;

  async function handleTranslate() {
    if (!store.input.text.trim()) return;
    if (insufficient) return;
    store.setIsTranslating(true);
    resetAll();

    for (const lang of store.languages) {
      setResult(lang, { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1 });
    }

    try {
      const literalMode = isLiteralMode(store.input.strategy);
      const data = await apiClient.post("/api/jobs", {
        source_text: store.input.text,
        genre: store.input.genre,
        strategy: store.input.strategy,
        target_languages: store.languages,
        cultural_sphere: literalMode ? null : store.input.culturalSphere,
        audience_type: literalMode ? null : store.input.audienceType,
      });
      store.setCurrentJobId(data.id);

      // Connect WebSocket for status updates
      wsClient.connect(data.id, (msg: any) => {
        if (msg.type === "status" && msg.results) {
          for (const r of msg.results) {
            if (r.status === "completed" || r.status === "failed") {
              setResult(r.language, { status: r.status });
            }
          }
        }
      });

      // Also poll for full results (WebSocket only sends status, not translated_text)
      pollJobStatus(data.id);
    } catch (err) {
      console.error("Translation failed:", err);
      if (err instanceof Error && err.message.includes("INSUFFICIENT_CREDITS")) {
        useCreditsStore.getState().fetchBalance();
      }
      store.setIsTranslating(false);
    }
  }

  async function pollJobStatus(jobId: string) {
    const poll = async () => {
      try {
        const data = await apiClient.get(`/api/jobs/${jobId}`);
        for (const r of data.results) {
          setResult(r.language, {
            status: r.status,
            translatedText: r.translated_text || "",
            riskAnnotations: r.risk_annotations || [],
            acceptanceScore: r.acceptance_score,
            culturalAdaptation: r.cultural_adaptation || null,
            resultId: r.id,   // 保存结果 ID，供 DecisionLogPanel 拉取决策日志
          });
        }
        if (data.status === "completed" || data.status === "failed" || data.status === "partial") {
          store.setIsTranslating(false);
          wsClient.disconnect();
          return;
        }
        setTimeout(poll, 2000);
      } catch {
        store.setIsTranslating(false);
      }
    };
    setTimeout(poll, 2000);
  }

  function toggleLanguage(code: string) {
    if (store.languages.includes(code)) {
      if (store.languages.length > 1) {
        store.setLanguages(store.languages.filter((l) => l !== code));
      }
    } else {
      store.setLanguages([...store.languages, code]);
    }
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <GenreSelector />
      <CultureSphereSelector />
      <AudienceTypeSelector />
      <FileUploadZone />
      <TextEditor />
      <StrategySelector />
      <div className="flex flex-wrap gap-1.5">
        {LANGUAGES.map((l) => (
          <button
            key={l.code}
            onClick={() => toggleLanguage(l.code)}
            className={`cursor-pointer rounded px-2.5 py-1 text-xs transition-all duration-200 active:scale-[0.95] ${
              store.languages.includes(l.code) ? "bg-terracotta text-white" : "bg-muted text-muted-foreground hover:bg-teal-lightest"
            }`}
          >
            {l.labelZh}
          </button>
        ))}
      </div>
      {insufficient && (
        <div className="rounded border border-danger bg-danger/5 p-3 text-sm text-danger">
          信用分已用完，翻译功能不可用，请联系管理员充值。
        </div>
      )}
      <Button
        onClick={handleTranslate}
        disabled={!store.input.text.trim() || store.isTranslating || store.upload.isUploading || insufficient}
        title={insufficient ? "信用分已用完，请联系管理员充值" : undefined}
        className="bg-teal hover:bg-teal-light text-white"
      >
        {store.isTranslating ? "转译中..." : "开始转译"}
      </Button>
    </div>
  );
}
