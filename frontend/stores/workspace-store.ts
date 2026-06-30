import { create } from "zustand";

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
  isTranslating: boolean;
  currentJobId: string | null;
  upload: UploadState;
  setText: (text: string) => void;
  setGenre: (genre: Genre) => void;
  setStrategy: (strategy: Strategy) => void;
  setCulturalSphere: (sphere: CulturalSphere) => void;
  setAudienceType: (audience: AudienceType) => void;
  setLanguages: (languages: string[]) => void;
  setIsTranslating: (v: boolean) => void;
  setCurrentJobId: (id: string | null) => void;
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
  isTranslating: false,
  currentJobId: null as string | null,
  upload: initialUploadState,
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  ...initialState,
  setText: (text) => set((s) => ({ input: { ...s.input, text } })),
  setGenre: (genre) => set((s) => ({ input: { ...s.input, genre } })),
  setStrategy: (strategy) => set((s) => ({ input: { ...s.input, strategy } })),
  setCulturalSphere: (culturalSphere) => set((s) => ({ input: { ...s.input, culturalSphere } })),
  setAudienceType: (audience) => set((s) => ({ input: { ...s.input, audienceType: audience } })),
  setLanguages: (languages) => set({ languages }),
  setIsTranslating: (isTranslating) => set({ isTranslating }),
  setCurrentJobId: (currentJobId) => set({ currentJobId }),
  setUploadState: (state) => set((s) => ({ upload: { ...s.upload, ...state } })),
  clearUpload: () => set({ upload: initialUploadState }),
  reset: () => set({ ...initialState, upload: initialUploadState }),
}));
