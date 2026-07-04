import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector?: (s: unknown) => unknown) => {
    const state = {
      input: { text: "测试", genre: "political", strategy: "semantic_equivalence", culturalSphere: "western_english", audienceType: "general_public" },
      languages: ["en-GB"],
      activeLanguage: "en-GB",
      isTranslating: false,
      currentJobId: null,
      upload: { isUploading: false },
      setText: vi.fn(),
      setGenre: vi.fn(),
      setStrategy: vi.fn(),
      setCulturalSphere: vi.fn(),
      setAudienceType: vi.fn(),
      setLanguages: vi.fn(),
      setActiveLanguage: vi.fn(),
      setIsTranslating: vi.fn(),
      setCurrentJobId: vi.fn(),
      loadFromHistory: vi.fn(),
      setUploadState: vi.fn(),
      clearUpload: vi.fn(),
      reset: vi.fn(),
    };
    return selector ? selector(state) : state;
  }),
}));

vi.mock("@/stores/translation-store", () => ({
  useTranslationStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector({ resetAll: vi.fn(), setResult: vi.fn() }),
  ),
}));

vi.mock("@/lib/ws-client", () => ({ wsClient: { connect: vi.fn(), disconnect: vi.fn() } }));

vi.mock("@/lib/api-client", () => ({
  apiClient: { post: vi.fn(), get: vi.fn() },
}));

vi.mock("@/stores/credits-store", () => ({
  useCreditsStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector({ balance: 0, isInsufficient: true }),
  ),
}));

import { InputPanel } from "../input-panel";

describe("InputPanel credits guard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows insufficient-credits alert when balance is 0", () => {
    render(<InputPanel />);
    expect(screen.getByText(/信用分已用完/)).toBeInTheDocument();
  });

  it("disables the translate button when balance is 0", () => {
    render(<InputPanel />);
    const btn = screen.getByRole("button", { name: /开始转译/ });
    expect(btn).toBeDisabled();
  });
});
