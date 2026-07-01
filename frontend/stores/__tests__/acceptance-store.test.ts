import { describe, it, expect, vi, beforeEach } from "vitest";
import { useTranslationStore } from "@/stores/translation-store";
import { apiClient } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    postAcceptanceScore: vi.fn(),
    postAcceptanceScoreDelta: vi.fn(),
  },
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: { getState: vi.fn(() => ({ currentJobId: "job-1" })) },
}));

describe("acceptance scoring store actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTranslationStore.getState().resetAll();
    useTranslationStore.getState().setResult("en-GB", { status: "completed", translatedText: "Hello." });
  });

  it("triggerFirstScoring sets score on success", async () => {
    (apiClient.postAcceptanceScore as ReturnType<typeof vi.fn>).mockResolvedValue({
      total_score: 80, dimensions: { audience: 20, cultural: 20, naturalness: 20, risk: 20 },
      confidence: 0.9, top3_risk_indices: [], audience_baseline: "policy_media",
    });
    const ok = await useTranslationStore.getState().triggerFirstScoring("en-GB", "policy_media");
    expect(ok).toBe(true);
    const r = useTranslationStore.getState().results["en-GB"];
    expect(r.acceptanceScore).toBe(80);
    expect(r.acceptanceConfidence).toBe(0.9);
    expect(r.audienceBaseline).toBe("policy_media");
    expect(r.isScoringAcceptance).toBe(false);
  });

  it("triggerFirstScoring returns false on failure, keeps -1", async () => {
    (apiClient.postAcceptanceScore as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("500"));
    const ok = await useTranslationStore.getState().triggerFirstScoring("en-GB", "policy_media");
    expect(ok).toBe(false);
    const r = useTranslationStore.getState().results["en-GB"];
    expect(r.acceptanceScore).toBe(-1);
    expect(r.isScoringAcceptance).toBe(false);
  });

  it("triggerDeltaScoring calls delta endpoint with risk_index", async () => {
    (apiClient.postAcceptanceScoreDelta as ReturnType<typeof vi.fn>).mockResolvedValue({
      total_score: 60, dimensions: { audience: 15, cultural: 15, naturalness: 15, risk: 15 },
      confidence: 0.5, top3_risk_indices: [0], audience_baseline: "policy_media",
    });
    const ok = await useTranslationStore.getState().triggerDeltaScoring("en-GB", 2);
    expect(ok).toBe(true);
    expect(apiClient.postAcceptanceScoreDelta).toHaveBeenCalledWith("job-1", { lang: "en-GB", risk_index: 2 });
    expect(useTranslationStore.getState().results["en-GB"].acceptanceScore).toBe(60);
  });

  it("triggerDeltaScoring returns false on failure, keeps old score", async () => {
    useTranslationStore.getState().setResult("en-GB", { acceptanceScore: 80 });
    (apiClient.postAcceptanceScoreDelta as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("500"));
    const ok = await useTranslationStore.getState().triggerDeltaScoring("en-GB", 0);
    expect(ok).toBe(false);
    expect(useTranslationStore.getState().results["en-GB"].acceptanceScore).toBe(80);
  });

  it("clearAcceptanceScore resets scoring fields", () => {
    useTranslationStore.getState().setResult("en-GB", { acceptanceScore: 80, audienceBaseline: "academic" });
    useTranslationStore.getState().clearAcceptanceScore("en-GB");
    const r = useTranslationStore.getState().results["en-GB"];
    expect(r.acceptanceScore).toBe(-1);
    expect(r.audienceBaseline).toBeUndefined();
  });

  it("triggerFirstScoring no-ops when no jobId", async () => {
    const { useWorkspaceStore } = await import("@/stores/workspace-store");
    (useWorkspaceStore.getState as ReturnType<typeof vi.fn>).mockReturnValueOnce({ currentJobId: null });
    const ok = await useTranslationStore.getState().triggerFirstScoring("en-GB", "policy_media");
    expect(ok).toBe(false);
    expect(apiClient.postAcceptanceScore).not.toHaveBeenCalled();
  });
});
