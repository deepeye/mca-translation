import { create } from "zustand";

export type Genre = "political" | "news" | "policy" | "brand";
export type Strategy = "semantic_equivalence" | "audience_first" | "literal_reference";

interface WorkspaceState {
  input: { text: string; genre: Genre; strategy: Strategy };
  languages: string[];
  isTranslating: boolean;
  currentJobId: string | null;
  setText: (text: string) => void;
  setGenre: (genre: Genre) => void;
  setStrategy: (strategy: Strategy) => void;
  setLanguages: (languages: string[]) => void;
  setIsTranslating: (v: boolean) => void;
  setCurrentJobId: (id: string | null) => void;
  reset: () => void;
}

const initialState = {
  input: { text: "", genre: "political" as Genre, strategy: "semantic_equivalence" as Strategy },
  languages: ["en-GB"],
  isTranslating: false,
  currentJobId: null,
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  ...initialState,
  setText: (text) => set((s) => ({ input: { ...s.input, text } })),
  setGenre: (genre) => set((s) => ({ input: { ...s.input, genre } })),
  setStrategy: (strategy) => set((s) => ({ input: { ...s.input, strategy } })),
  setLanguages: (languages) => set({ languages }),
  setIsTranslating: (isTranslating) => set({ isTranslating }),
  setCurrentJobId: (currentJobId) => set({ currentJobId }),
  reset: () => set(initialState),
}));
