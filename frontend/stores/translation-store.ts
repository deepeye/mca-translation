import { create } from "zustand";
import { apiClient, type DecisionLogEntry, type AudienceBaseline, type DimensionScores, type AcceptanceScorePayload } from "@/lib/api-client";
import { useWorkspaceStore } from "@/stores/workspace-store";

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
  resultId?: string;          // 新增：译文结果 ID，用于拉取决策日志
  status: ResultStatus;
  translatedText: string;
  riskAnnotations: RiskAnnotation[];
  acceptanceScore: number;
  acceptanceDimensions?: DimensionScores;
  acceptanceConfidence?: number;
  acceptanceTop3Risks?: number[];
  audienceBaseline?: AudienceBaseline;
  isScoringAcceptance?: boolean;
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
    id: string;                // 译文结果 ID，用于拉取决策日志
    language: string;
    status: string;
    translated_text: string | null;
    risk_annotations: RiskAnnotation[] | null;
    acceptance_score: number;
    cultural_adaptation: CulturalAdaptation | null;
  }>) => void;
  decisionLogs: DecisionLogEntry[];
  isLoadingDecisions: boolean;
  loadDecisionLogs: (resultId: string) => Promise<void>;
  clearDecisionLogs: () => void;
  triggerFirstScoring: (lang: string, audienceBaseline: AudienceBaseline) => Promise<boolean>;
  triggerDeltaScoring: (lang: string, riskIndex: number) => Promise<boolean>;
  setAcceptanceScore: (lang: string, payload: AcceptanceScorePayload) => void;
  clearAcceptanceScore: (lang: string) => void;
}

export const useTranslationStore = create<TranslationState>((set) => ({
  results: {},
  setResult: (lang, result) =>
    set((s) => {
      const defaults: LangResult = { status: "idle", translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
      const existing = s.results[lang] || defaults;
      // status 回到 idle 时（新一次转译）清空评分字段
      if (result.status === "idle") {
        return { results: { ...s.results, [lang]: { ...defaults, ...result } } };
      }
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
          resultId: r.id,      // 保存结果 ID，供 DecisionLogPanel 拉取决策日志
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
  decisionLogs: [],
  isLoadingDecisions: false,

  loadDecisionLogs: async (resultId: string) => {
    set({ isLoadingDecisions: true });
    try {
      const logs = await apiClient.getResultDecisions(resultId);
      set({ decisionLogs: logs, isLoadingDecisions: false });
    } catch {
      // 尽力而为 — 失败时显示空状态
      set({ decisionLogs: [], isLoadingDecisions: false });
    }
  },

  clearDecisionLogs: () => set({ decisionLogs: [] }),

  triggerFirstScoring: async (lang, audienceBaseline) => {
    const jobId = useWorkspaceStore.getState().currentJobId;
    if (!jobId) return false;
    set((s) => {
      const existing = s.results[lang] || { status: "idle" as ResultStatus, translatedText: "", riskAnnotations: [], acceptanceScore: -1, highlightedIndex: null, culturalAdaptation: null };
      return { results: { ...s.results, [lang]: { ...existing, isScoringAcceptance: true } } };
    });
    try {
      const payload = await apiClient.postAcceptanceScore(jobId, { lang, audience_baseline: audienceBaseline });
      set((s) => {
        const existing = s.results[lang];
        if (!existing) return {};
        return { results: { ...s.results, [lang]: {
          ...existing,
          acceptanceScore: payload.total_score,
          acceptanceDimensions: payload.dimensions,
          acceptanceConfidence: payload.confidence,
          acceptanceTop3Risks: payload.top3_risk_indices,
          audienceBaseline: payload.audience_baseline,
          isScoringAcceptance: false,
        } } };
      });
      return true;
    } catch (e) {
      console.error("acceptance first scoring failed", e);
      set((s) => {
        const existing = s.results[lang];
        if (!existing) return {};
        return { results: { ...s.results, [lang]: { ...existing, isScoringAcceptance: false } } };
      });
      return false;
    }
  },
  triggerDeltaScoring: async (lang, riskIndex) => {
    const jobId = useWorkspaceStore.getState().currentJobId;
    if (!jobId) return false;
    set((s) => {
      const existing = s.results[lang];
      if (!existing) return {};
      return { results: { ...s.results, [lang]: { ...existing, isScoringAcceptance: true } } };
    });
    try {
      const payload = await apiClient.postAcceptanceScoreDelta(jobId, { lang, risk_index: riskIndex });
      set((s) => {
        const existing = s.results[lang];
        if (!existing) return {};
        return { results: { ...s.results, [lang]: {
          ...existing,
          acceptanceScore: payload.total_score,
          acceptanceDimensions: payload.dimensions,
          acceptanceConfidence: payload.confidence,
          acceptanceTop3Risks: payload.top3_risk_indices,
          audienceBaseline: payload.audience_baseline,
          isScoringAcceptance: false,
        } } };
      });
      return true;
    } catch (e) {
      console.error("acceptance delta scoring failed", e);
      set((s) => {
        const existing = s.results[lang];
        if (!existing) return {};
        return { results: { ...s.results, [lang]: { ...existing, isScoringAcceptance: false } } };
      });
      return false;
    }
  },
  setAcceptanceScore: (lang, payload) =>
    set((s) => {
      const existing = s.results[lang];
      if (!existing) return {};
      return { results: { ...s.results, [lang]: {
        ...existing,
        acceptanceScore: payload.total_score,
        acceptanceDimensions: payload.dimensions,
        acceptanceConfidence: payload.confidence,
        acceptanceTop3Risks: payload.top3_risk_indices,
        audienceBaseline: payload.audience_baseline,
        isScoringAcceptance: false,
      } } };
    }),
  clearAcceptanceScore: (lang) =>
    set((s) => {
      const existing = s.results[lang];
      if (!existing) return {};
      return { results: { ...s.results, [lang]: {
        ...existing,
        acceptanceScore: -1,
        acceptanceDimensions: undefined,
        acceptanceConfidence: undefined,
        acceptanceTop3Risks: undefined,
        audienceBaseline: undefined,
        isScoringAcceptance: false,
      } } };
    }),
}));
