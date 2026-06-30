import { create } from "zustand";

export type ResultStatus = "idle" | "streaming" | "completed" | "failed" | "partial";

export interface RiskAnnotation {
  phrase: string;
  risk_level: "low" | "medium" | "high";
  risk_type: string;
  explanation: string;
  status: "open" | "accepted" | "dismissed";
  accepted_suggestion?: string;
  offset?: number;
}

export interface RiskSpan {
  index: number;
  phrase: string;
  offset: number;
  length: number;
  risk_level: "low" | "medium" | "high";
  risk_type: string;
  explanation: string;
  status?: "open" | "accepted" | "dismissed";
}

export type AdaptationStrategy = "literal" | "explanatory" | "analogical" | "reconstruction";

export interface CulturalLoadedTerm {
  term: string;
  culture_gap: "low" | "medium" | "high";
  adaptation_strategy: AdaptationStrategy;
  suggested_rendering: string;
  reason: string;
}

export interface CulturalAdaptation {
  culture_loaded_terms: CulturalLoadedTerm[];
  cultural_notes: string[];
  taboo_warnings: string[];
}

interface LangResult {
  status: ResultStatus;
  translatedText: string;
  riskAnnotations: RiskAnnotation[];
  acceptanceScore: number;
  highlightedIndex: number | null;
  culturalAdaptation: CulturalAdaptation | null;
}

interface TranslationState {
  results: Record<string, LangResult>;
  setResult: (lang: string, result: Partial<LangResult>) => void;
  appendText: (lang: string, delta: string) => void;
  resetAll: () => void;
  acceptRisk: (lang: string, riskIndex: number, suggestion: string, translatedText: string, annotations: RiskAnnotation[]) => void;
  dismissRisk: (lang: string, riskIndex: number, annotations: RiskAnnotation[]) => void;
  revertRisk: (lang: string, riskIndex: number, translatedText: string, annotations: RiskAnnotation[]) => void;
  setAnnotations: (lang: string, annotations: RiskAnnotation[]) => void;
  loadFromHistory: (results: Array<{
    language: string;
    status: string;
    translated_text: string | null;
    risk_annotations: RiskAnnotation[] | null;
    acceptance_score: number;
    cultural_adaptation: CulturalAdaptation | null;
  }>) => void;
}

export const useTranslationStore = create<TranslationState>((set) => ({
  results: {},
  setResult: (lang, result) =>
    set((s) => {
      const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
      const existing = s.results[lang] || defaults;
      return { results: { ...s.results, [lang]: { ...existing, ...result } } };
    }),
  appendText: (lang, delta) =>
    set((s) => {
      const existing = s.results[lang] || { status: "streaming" as ResultStatus, translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
      return { results: { ...s.results, [lang]: { ...existing, translatedText: existing.translatedText + delta, status: "streaming" } } };
    }),
  resetAll: () => set({ results: {} }),
  acceptRisk: (lang, riskIndex, suggestion, translatedText, annotations) =>
    set((s) => {
      const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
      const existing = s.results[lang] || defaults;
      return { results: { ...s.results, [lang]: { ...existing, translatedText, riskAnnotations: annotations } } };
    }),
  dismissRisk: (lang, riskIndex, annotations) =>
    set((s) => {
      const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
      const existing = s.results[lang] || defaults;
      return { results: { ...s.results, [lang]: { ...existing, riskAnnotations: annotations } } };
    }),
  revertRisk: (lang, riskIndex, translatedText, annotations) =>
    set((s) => {
      const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
      const existing = s.results[lang] || defaults;
      return { results: { ...s.results, [lang]: { ...existing, translatedText, riskAnnotations: annotations } } };
    }),
  setAnnotations: (lang, annotations) =>
    set((s) => {
      const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
      const existing = s.results[lang] || defaults;
      return { results: { ...s.results, [lang]: { ...existing, riskAnnotations: annotations } } };
    }),
  loadFromHistory: (results) =>
    set((s) => {
      const newResults: Record<string, LangResult> = {};
      for (const r of results) {
        newResults[r.language] = {
          status: r.status as ResultStatus,
          translatedText: r.translated_text || "",
          riskAnnotations: r.risk_annotations || [],
          acceptanceScore: r.acceptance_score,
          highlightedIndex: null,
          culturalAdaptation: r.cultural_adaptation,
        };
      }
      return { results: { ...s.results, ...newResults } };
    }),
}));
