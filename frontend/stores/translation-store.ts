import { create } from "zustand";

export type ResultStatus = "idle" | "streaming" | "completed" | "failed" | "partial";

interface RiskAnnotation {
  phrase: string;
  risk_level: "low" | "medium" | "high";
  risk_type: "cognitive_bias" | "negative_association" | "ambiguity";
  explanation: string;
}

interface LangResult {
  status: ResultStatus;
  translatedText: string;
  riskAnnotations: RiskAnnotation[];
  acceptanceScore: number;
}

interface TranslationState {
  results: Record<string, LangResult>;
  setResult: (lang: string, result: Partial<LangResult>) => void;
  appendText: (lang: string, delta: string) => void;
  resetAll: () => void;
}

export const useTranslationStore = create<TranslationState>((set) => ({
  results: {},
  setResult: (lang, result) =>
    set((s) => ({
      results: { ...s.results, [lang]: { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, ...result } },
    })),
  appendText: (lang, delta) =>
    set((s) => {
      const existing = s.results[lang] || { status: "streaming" as ResultStatus, translatedText: "", riskAnnotations: [], acceptanceScore: -1 };
      return { results: { ...s.results, [lang]: { ...existing, translatedText: existing.translatedText + delta, status: "streaming" } } };
    }),
  resetAll: () => set({ results: {} }),
}));
