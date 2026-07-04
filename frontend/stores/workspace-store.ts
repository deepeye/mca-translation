import { create } from "zustand";
import { affinitySphereFor } from "@/lib/languages";

export type Genre = "political" | "news" | "policy" | "brand";
export type Strategy = "semantic_equivalence" | "audience_first" | "literal_reference";
export type CulturalSphere =
  | "western_english"
  | "european_continental"
  | "islamic_middle_east"
  | "east_asian_confucian"
  | "latin_american"
  | "russian_sphere"
  | "south_asian"
  | "african";
export type AudienceType =
  | "general_public"
  | "media"
  | "government"
  | "academic"
  | "business"
  | "diaspora_chinese";

export type UploadState = {
  file: File | null;
  fileId: string | null;
  fileName: string | null;
  fileSize: number | null;
  isUploading: boolean;
  uploadError: string | null;
};

interface WorkspaceInput {
  text: string;
  genre: Genre;
  strategy: Strategy;
  culturalSphere: CulturalSphere;
  audienceType: AudienceType;
}

interface WorkspaceState {
  input: WorkspaceInput;
  languages: string[];
  activeLanguage: string;
  sphereTouched: boolean;
  isTranslating: boolean;
  currentJobId: string | null;
  upload: UploadState;
  setText: (text: string) => void;
  setGenre: (genre: Genre) => void;
  setStrategy: (strategy: Strategy) => void;
  setCulturalSphere: (sphere: CulturalSphere) => void;
  setAudienceType: (audience: AudienceType) => void;
  setLanguages: (languages: string[]) => void;
  setActiveLanguage: (lang: string) => void;
  setIsTranslating: (v: boolean) => void;
  setCurrentJobId: (id: string | null) => void;
  loadFromHistory: (job: {
    id: string;
    source_text: string;
    genre: string;
    strategy: string;
    cultural_sphere?: string | null;
    audience_type?: string | null;
    target_languages: string[];
  }) => void;
  setUploadState: (state: Partial<UploadState>) => void;
  clearUpload: () => void;
  reset: () => void;
}

const initialUploadState: UploadState = {
  file: null,
  fileId: null,
  fileName: null,
  fileSize: null,
  isUploading: false,
  uploadError: null,
};

const initialState = {
  input: {
    text: "",
    genre: "political" as Genre,
    strategy: "semantic_equivalence" as Strategy,
    culturalSphere: "western_english" as CulturalSphere,
    audienceType: "general_public" as AudienceType,
  },
  languages: ["en-GB"],
  activeLanguage: "en-GB",
  sphereTouched: false,
  isTranslating: false,
  currentJobId: null as string | null,
  upload: initialUploadState,
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  ...initialState,
  setText: (text) => set((s) => ({ input: { ...s.input, text } })),
  setGenre: (genre) => set((s) => ({ input: { ...s.input, genre } })),
  setStrategy: (strategy) => set((s) => ({ input: { ...s.input, strategy } })),
  setCulturalSphere: (culturalSphere) =>
    set((s) => ({ input: { ...s.input, culturalSphere }, sphereTouched: true })),
  setAudienceType: (audience) => set((s) => ({ input: { ...s.input, audienceType: audience } })),
  setActiveLanguage: (activeLanguage) => set({ activeLanguage }),
  setLanguages: (languages) =>
    set((s) => {
      const next: { languages: string[]; input?: typeof s.input; activeLanguage?: string } = { languages };
      if (!s.sphereTouched && languages.length > 0) {
        const affinity = languages
          .map((code) => affinitySphereFor(code))
          .find((a): a is string => a !== null);
        if (affinity) {
          next.input = { ...s.input, culturalSphere: affinity as CulturalSphere };
        }
      }
      const newActive = languages.find((l) => l === s.activeLanguage) || languages[0] || "en-GB";
      next.activeLanguage = newActive;
      return next;
    }),
  setIsTranslating: (isTranslating) => set({ isTranslating }),
  setCurrentJobId: (currentJobId) => set({ currentJobId }),
  loadFromHistory: (job) =>
    set({
      input: {
        text: job.source_text,
        genre: job.genre as Genre,
        strategy: job.strategy as Strategy,
        culturalSphere: (job.cultural_sphere || "western_english") as CulturalSphere,
        audienceType: (job.audience_type || "general_public") as AudienceType,
      },
      languages: job.target_languages,
      activeLanguage: job.target_languages[0] || "en-GB",
      sphereTouched: true,
      currentJobId: job.id,
      isTranslating: false,
    }),
  setUploadState: (state) => set((s) => ({ upload: { ...s.upload, ...state } })),
  clearUpload: () => set({ upload: initialUploadState }),
  reset: () => set({ ...initialState, upload: initialUploadState }),
}));
