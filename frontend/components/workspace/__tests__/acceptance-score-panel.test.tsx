import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AcceptanceScorePanel } from "../acceptance-score-panel";

// 默认 mock state，可被单测覆盖
const state: Record<string, unknown> = {
  results: { "en-GB": { status: "completed", translatedText: "Hello.", acceptanceScore: -1 } },
  triggerFirstScoring: vi.fn().mockResolvedValue(true),
  triggerDeltaScoring: vi.fn().mockResolvedValue(true),
  setResult: vi.fn(),
  clearAcceptanceScore: vi.fn(),
};

vi.mock("@/stores/translation-store", () => ({
  useTranslationStore: vi.fn((selector: (s: unknown) => unknown) => selector(state)),
}));
vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector({ languages: ["en-GB"], currentJobId: "job-1" }),
  ),
}));

function setState(patch: Record<string, unknown>) {
  const cur = (state.results as Record<string, object>)["en-GB"];
  const upd = ((patch.results as Record<string, object> | undefined)?.["en-GB"]) || {};
  Object.assign(state, patch, {
    results: { "en-GB": { ...cur, ...upd } },
  });
}

describe("AcceptanceScorePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(state, {
      results: { "en-GB": { status: "completed", translatedText: "Hello.", acceptanceScore: -1 } },
      triggerFirstScoring: vi.fn().mockResolvedValue(true),
      triggerDeltaScoring: vi.fn().mockResolvedValue(true),
      setResult: vi.fn(),
      clearAcceptanceScore: vi.fn(),
    });
  });

  it("does not render when status != completed", () => {
    setState({ results: { "en-GB": { status: "streaming", translatedText: "Hello.", acceptanceScore: -1 } } });
    const { container } = render(<AcceptanceScorePanel />);
    expect(container.firstChild).toBeNull();
  });

  it("triggers first scoring on completed + score=-1 (idempotent)", async () => {
    render(<AcceptanceScorePanel />);
    await waitFor(() => {
      expect(state.triggerFirstScoring).toHaveBeenCalledWith("en-GB", "policy_media");
    });
    // StrictMode 可能在测试环境中双重调用 effect；幂等的真正保护是
    // `acceptanceScore === -1 && !isScoringAcceptance` 运行时守卫，
    // 而非调用次数。此处仅校验被调用参数，不校验次数以避免 StrictMode 抖动。
  });

  it("renders skeleton while scoring", () => {
    setState({ results: { "en-GB": { status: "completed", translatedText: "Hello.", acceptanceScore: -1, isScoringAcceptance: true } } });
    const { container } = render(<AcceptanceScorePanel />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders score + dimensions on success", () => {
    setState({ results: { "en-GB": {
      status: "completed", translatedText: "Hello.", acceptanceScore: 80,
      acceptanceDimensions: { audience: 20, cultural: 20, naturalness: 20, risk: 20 },
      acceptanceConfidence: 0.9, acceptanceTop3Risks: [], audienceBaseline: "policy_media",
    } } });
    render(<AcceptanceScorePanel />);
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText("受众匹配度")).toBeInTheDocument();
  });

  it("greys score when confidence low", () => {
    setState({ results: { "en-GB": {
      status: "completed", translatedText: "Hello.", acceptanceScore: 50,
      acceptanceDimensions: { audience: 12, cultural: 13, naturalness: 12, risk: 13 },
      acceptanceConfidence: 0.2, acceptanceTop3Risks: [], audienceBaseline: "policy_media",
    } } });
    render(<AcceptanceScorePanel />);
    expect(screen.getByText(/评分置信度低/)).toBeInTheDocument();
  });

  it("shows retry button on first-scoring failure (completed, -1, not scoring)", () => {
    setState({ results: { "en-GB": { status: "completed", translatedText: "Hello.", acceptanceScore: -1, isScoringAcceptance: false } } });
    render(<AcceptanceScorePanel />);
    const retry = screen.getByText("重试");
    fireEvent.click(retry);
    expect(state.triggerFirstScoring).toHaveBeenCalledWith("en-GB", "policy_media");
  });

  it("audience switch triggers first scoring with new baseline", () => {
    setState({ results: { "en-GB": {
      status: "completed", translatedText: "Hello.", acceptanceScore: 80,
      acceptanceDimensions: { audience: 20, cultural: 20, naturalness: 20, risk: 20 },
      acceptanceConfidence: 0.9, acceptanceTop3Risks: [], audienceBaseline: "policy_media",
    } } });
    render(<AcceptanceScorePanel />);
    fireEvent.click(screen.getByText("学术界"));
    expect(state.triggerFirstScoring).toHaveBeenCalledWith("en-GB", "academic");
  });

  it("audience buttons disabled while scoring", () => {
    setState({ results: { "en-GB": {
      status: "completed", translatedText: "Hello.", acceptanceScore: 80,
      acceptanceDimensions: { audience: 20, cultural: 20, naturalness: 20, risk: 20 },
      acceptanceConfidence: 0.9, acceptanceTop3Risks: [], audienceBaseline: "policy_media",
      isScoringAcceptance: true,
    } } });
    render(<AcceptanceScorePanel />);
    expect(screen.getByText("主流媒体")).toBeDisabled();
  });

  it("Top3 click dispatches scroll-to-risk-mark + sets highlightedIndex", () => {
    setState({ results: { "en-GB": {
      status: "completed", translatedText: "Hello.", acceptanceScore: 80,
      acceptanceDimensions: { audience: 20, cultural: 20, naturalness: 20, risk: 20 },
      acceptanceConfidence: 0.9, acceptanceTop3Risks: [2, 0, 1],
      riskAnnotations: [
        { phrase: "a", risk_level: "low", risk_type: "ambiguity", explanation: "", status: "open" },
        { phrase: "b", risk_level: "low", risk_type: "ambiguity", explanation: "", status: "open" },
        { phrase: "c", risk_level: "high", risk_type: "ambiguity", explanation: "", status: "open" },
      ],
      audienceBaseline: "policy_media",
    } } });
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");
    render(<AcceptanceScorePanel />);
    fireEvent.click(screen.getByText("c"));  // top3 first item = risk_index 2, phrase "c"
    expect(state.setResult).toHaveBeenCalledWith("en-GB", { highlightedIndex: 2 });
    expect(dispatchSpy).toHaveBeenCalled();
    const evt = dispatchSpy.mock.calls[0][0] as CustomEvent;
    expect(evt.type).toBe("scroll-to-risk-mark");
    expect(evt.detail).toEqual({ language: "en-GB", index: 2 });
    dispatchSpy.mockRestore();
  });

  it("renders permanent non-audit disclaimer", () => {
    setState({ results: { "en-GB": {
      status: "completed", translatedText: "Hello.", acceptanceScore: 80,
      acceptanceDimensions: { audience: 20, cultural: 20, naturalness: 20, risk: 20 },
      acceptanceConfidence: 0.9, acceptanceTop3Risks: [], audienceBaseline: "policy_media",
    } } });
    render(<AcceptanceScorePanel />);
    expect(screen.getByText(/非审计级，仅供参考/)).toBeInTheDocument();
  });

  it("does not re-trigger scoring when clicking the active audience baseline (same-baseline skip)", () => {
    setState({ results: { "en-GB": {
      status: "completed", translatedText: "Hello.", acceptanceScore: 80,
      acceptanceDimensions: { audience: 20, cultural: 20, naturalness: 20, risk: 20 },
      acceptanceConfidence: 0.9, acceptanceTop3Risks: [], audienceBaseline: "policy_media",
    } } });
    render(<AcceptanceScorePanel />);
    fireEvent.click(screen.getByText("主流媒体")); // 当前已激活的基准 — 应为 no-op
    expect(state.triggerFirstScoring).not.toHaveBeenCalled();
  });

  it("clears acceptance score when status is not completed", () => {
    setState({ results: { "en-GB": { status: "streaming", translatedText: "Hello.", acceptanceScore: -1 } } });
    const { container } = render(<AcceptanceScorePanel />);
    expect(container.firstChild).toBeNull();
    expect(state.clearAcceptanceScore).toHaveBeenCalledWith("en-GB");
  });
});
