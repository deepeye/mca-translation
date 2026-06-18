import { create } from "zustand";

export interface DetectedTerm {
  source_term: string;
  term_type: string;
  risk_notes: string;
  translations: Record<string, { preferred: string; notes: string; alternatives: string[] }>;
}

interface GlossaryState {
  detectedTerms: DetectedTerm[];
  isLoading: boolean;
  hoveredTerm: string | null;
  setDetectedTerms: (terms: DetectedTerm[]) => void;
  setIsLoading: (v: boolean) => void;
  setHoveredTerm: (term: string | null) => void;
}

export const useGlossaryStore = create<GlossaryState>((set) => ({
  detectedTerms: [],
  isLoading: false,
  hoveredTerm: null,
  setDetectedTerms: (terms) => set({ detectedTerms: terms }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setHoveredTerm: (hoveredTerm) => set({ hoveredTerm }),
}));
