import { create } from "zustand";

export type ResultStatus = "idle" | "streaming" | "completed" | "failed" | "partial";

export interface RiskAnnotation {
  phrase: string;
  risk_level: "low" | "medium" | "high";
  risk_type: string;
  explanation: string;
}

export interface RiskSpan {
  index: number;
  phrase: string;
  offset: number;
  length: number;
  risk_level: "low" | "medium" | "high";
  risk_type: string;
  explanation: string;
}

interface LangResult {
  status: ResultStatus;
  translatedText: string;
  riskAnnotations: RiskAnnotation[];
  acceptanceScore: number;
  highlightedIndex: number | null;
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
    set((s) => {
      const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null };
      const existing = s.results[lang] || defaults;
      return { results: { ...s.results, [lang]: { ...existing, ...result } } };
    }),
  appendText: (lang, delta) =>
    set((s) => {
      const existing = s.results[lang] || { status: "streaming" as ResultStatus, translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null };
      return { results: { ...s.results, [lang]: { ...existing, translatedText: existing.translatedText + delta, status: "streaming" } } };
    }),
  resetAll: () => set({ results: {} }),
}));
