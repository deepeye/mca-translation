import { create } from "zustand";

export type ReviewMode = "dual" | "single";
export type ReviewSeverity = "low" | "medium" | "high";

export interface ReviewIssue {
  category: string;
  severity: ReviewSeverity;
  span: { start: number; end: number; text: string } | null;
  original: string;
  suggestion: string;
  explanation: string;
  source_reference: string | null;
}

export interface ReviewCategory {
  name: string;
  score: number;
  issue_count: number;
  issues: ReviewIssue[];
}

export interface ReviewResult {
  review_id: string;
  mode: ReviewMode;
  overall_score: number;
  translated_text: string;
  target_language: string;
  audience_baseline: string;
  categories: ReviewCategory[];
  summary: string;
  created_at: string;
}

interface ReviewState {
  mode: ReviewMode;
  sourceText: string;
  translatedText: string;
  targetLanguage: string;
  genre: string;
  culturalSphere: string;
  audienceType: string;
  result: ReviewResult | null;
  highlightedIssueIndex: number | null;
  isLoading: boolean;
  error: string | null;

  setMode: (mode: ReviewMode) => void;
  setSourceText: (text: string) => void;
  setTranslatedText: (text: string) => void;
  setTargetLanguage: (lang: string) => void;
  setGenre: (genre: string) => void;
  setCulturalSphere: (sphere: string) => void;
  setAudienceType: (audience: string) => void;
  setResult: (result: ReviewResult | null) => void;
  setHighlightedIssue: (index: number | null) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  mode: "dual" as ReviewMode,
  sourceText: "",
  translatedText: "",
  targetLanguage: "en-GB",
  genre: "political",
  culturalSphere: "western_english",
  audienceType: "government",
  result: null as ReviewResult | null,
  highlightedIssueIndex: null as number | null,
  isLoading: false,
  error: null as string | null,
};

export const useReviewStore = create<ReviewState>((set) => ({
  ...initialState,
  setMode: (mode) => set({ mode }),
  setSourceText: (text) => set({ sourceText: text }),
  setTranslatedText: (text) => set({ translatedText: text }),
  setTargetLanguage: (lang) => set({ targetLanguage: lang }),
  setGenre: (genre) => set({ genre }),
  setCulturalSphere: (sphere) => set({ culturalSphere: sphere }),
  setAudienceType: (audience) => set({ audienceType: audience }),
  setResult: (result) => set({ result }),
  setHighlightedIssue: (index) => set({ highlightedIssueIndex: index }),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}));
