import { create } from "zustand";
import type { CulturalTermResult } from "@/lib/api-client";

export interface DetectedTerm {
  source_term: string;
  term_type: string;
  risk_notes: string;
  translations: Record<string, { preferred: string; notes: string; alternatives: string[] }>;
}

// 输入期 LLM 文化负载词分析状态机：
// idle → loading → analyzed；文本变更后 analyzed → stale（提示用户重新分析）
export type CulturalAnalysisState = "idle" | "loading" | "analyzed" | "stale";

interface GlossaryState {
  detectedTerms: DetectedTerm[];
  isLoading: boolean;
  hoveredTerm: string | null;
  setDetectedTerms: (terms: DetectedTerm[]) => void;
  setIsLoading: (v: boolean) => void;
  setHoveredTerm: (term: string | null) => void;

  // 文化负载词（LLM 识别，带文本偏移）
  culturalTerms: CulturalTermResult[];
  culturalAnalysisState: CulturalAnalysisState;
  setCulturalTerms: (terms: CulturalTermResult[]) => void;
  setCulturalAnalysisState: (s: CulturalAnalysisState) => void;
  clearHighlights: () => void;
}

export const useGlossaryStore = create<GlossaryState>((set) => ({
  detectedTerms: [],
  isLoading: false,
  hoveredTerm: null,
  setDetectedTerms: (terms) => set({ detectedTerms: terms }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setHoveredTerm: (hoveredTerm) => set({ hoveredTerm }),

  culturalTerms: [],
  culturalAnalysisState: "idle",
  setCulturalTerms: (culturalTerms) => set({ culturalTerms }),
  setCulturalAnalysisState: (culturalAnalysisState) =>
    set({ culturalAnalysisState }),
  // 丢弃已识别结果，回到 idle —— 重新高亮需再次手动分析
  clearHighlights: () =>
    set({
      detectedTerms: [],
      culturalTerms: [],
      culturalAnalysisState: "idle",
      hoveredTerm: null,
    }),
}));
