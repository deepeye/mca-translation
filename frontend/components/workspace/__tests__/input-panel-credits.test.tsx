import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const workspaceState = vi.hoisted(() => ({
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
}));

const translationState = vi.hoisted(() => ({
  resetAll: vi.fn(),
  setResult: vi.fn(),
}));

const creditsState = vi.hoisted(() => ({
  balance: 0,
  isInsufficient: true,
  fetchBalance: vi.fn(),
}));

const useCreditsStoreMock = vi.hoisted(() => {
  const fn = vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(creditsState) : creditsState,
  );
  (fn as unknown as { getState: ReturnType<typeof vi.fn> }).getState = vi.fn(() => creditsState);
  return fn;
});

const apiClient = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(workspaceState) : workspaceState,
  ),
}));

vi.mock("@/stores/translation-store", () => ({
  useTranslationStore: vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(translationState) : translationState,
  ),
}));

vi.mock("@/stores/credits-store", () => ({
  useCreditsStore: useCreditsStoreMock,
}));

vi.mock("@/lib/ws-client", () => ({ wsClient: { connect: vi.fn(), disconnect: vi.fn() } }));

vi.mock("@/lib/api-client", () => ({
  apiClient,
}));

import { InputPanel } from "../input-panel";

describe("InputPanel credits guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspaceState.input = { text: "测试", genre: "political", strategy: "semantic_equivalence", culturalSphere: "western_english", audienceType: "general_public" };
    workspaceState.languages = ["en-GB"];
    workspaceState.isTranslating = false;
    creditsState.balance = 0;
    creditsState.isInsufficient = true;
  });

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

describe("InputPanel 402 handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspaceState.input = { text: "测试", genre: "political", strategy: "semantic_equivalence", culturalSphere: "western_english", audienceType: "general_public" };
    workspaceState.languages = ["en-GB", "fr-FR"];
    workspaceState.isTranslating = false;
    creditsState.balance = 5;
    creditsState.isInsufficient = false;
    apiClient.post.mockRejectedValue(new Error("INSUFFICIENT_CREDITS"));
  });

  it("marks results as failed with credit error message when backend returns 402", async () => {
    render(<InputPanel />);
    const btn = screen.getByRole("button", { name: /开始转译/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(translationState.setResult).toHaveBeenCalledWith("en-GB", expect.objectContaining({ status: "failed", errorMessage: "余额不足，请联系管理员充值" }));
      expect(translationState.setResult).toHaveBeenCalledWith("fr-FR", expect.objectContaining({ status: "failed", errorMessage: "余额不足，请联系管理员充值" }));
    });
  });

  it("refreshes balance when backend returns 402", async () => {
    render(<InputPanel />);
    const btn = screen.getByRole("button", { name: /开始转译/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(creditsState.fetchBalance).toHaveBeenCalled();
    });
  });

  it("stops translating spinner when backend returns 402", async () => {
    render(<InputPanel />);
    const btn = screen.getByRole("button", { name: /开始转译/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(workspaceState.setIsTranslating).toHaveBeenCalledWith(false);
    });
  });
});
