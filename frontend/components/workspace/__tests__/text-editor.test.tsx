import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const workspaceState = vi.hoisted(() => ({
  input: {
    text: "构建人类命运共同体",
    culturalSphere: "western_english",
    audienceType: "general_public",
    genre: "political",
  },
}));

const glossaryState = vi.hoisted(() => ({
  detectedTerms: [] as any[],
  culturalTerms: [] as any[],
  culturalAnalysisState: "idle" as string,
  setDetectedTerms: vi.fn((terms: any[]) => {
    glossaryState.detectedTerms = terms;
  }),
  setCulturalTerms: vi.fn((terms: any[]) => {
    glossaryState.culturalTerms = terms;
  }),
  setCulturalAnalysisState: vi.fn((s: any) => {
    glossaryState.culturalAnalysisState = s;
  }),
  setHoveredTerm: vi.fn(),
  hoveredTerm: null,
  isLoading: false,
  setIsLoading: vi.fn(),
  clearHighlights: vi.fn(() => {
    glossaryState.detectedTerms = [];
    glossaryState.culturalTerms = [];
    glossaryState.culturalAnalysisState = "idle";
    glossaryState.hoveredTerm = null;
  }),
}));

const apiClient = vi.hoisted(() => ({
  detectTerms: vi.fn(),
  detectCulturalTerms: vi.fn(),
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(workspaceState) : workspaceState,
  ),
}));

vi.mock("@/stores/glossary-store", () => ({
  useGlossaryStore: vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(glossaryState) : glossaryState,
  ),
}));

vi.mock("@/lib/api-client", () => ({ apiClient }));

// InlineHighlighter and TermHighlighter render nothing with empty stores
vi.mock("../inline-highlighter", () => ({ InlineHighlighter: () => <div data-testid="inline-highlighter" /> }));
vi.mock("../term-highlighter", () => ({ TermHighlighter: () => <div data-testid="term-highlighter" /> }));

import { TextEditor } from "../text-editor";

describe("TextEditor manual detection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    glossaryState.detectedTerms = [];
    glossaryState.culturalTerms = [];
    glossaryState.culturalAnalysisState = "idle";
    workspaceState.input.text = "构建人类命运共同体";
    apiClient.detectTerms.mockResolvedValue({ terms: [] });
    apiClient.detectCulturalTerms.mockResolvedValue({ terms: [] });
  });

  it("does not auto-detect on render", () => {
    render(<TextEditor />);
    expect(apiClient.detectTerms).not.toHaveBeenCalled();
    expect(apiClient.detectCulturalTerms).not.toHaveBeenCalled();
  });

  it("calls both detect endpoints when analyze button is clicked", async () => {
    apiClient.detectTerms.mockResolvedValue({
      terms: [{ source_term: "人类命运共同体", term_type: "political_discourse", risk_notes: "", translations: {} }],
    });
    apiClient.detectCulturalTerms.mockResolvedValue({
      terms: [{ term: "人类命运共同体", offset: 2, length: 7, culture_gap: "high", adaptation_strategy: "explanatory", suggested_rendering: "x", reason: "r", term_type: "cultural_metaphor" }],
    });

    render(<TextEditor />);
    const btn = screen.getByRole("button", { name: /分析术语与文化负载词/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(apiClient.detectTerms).toHaveBeenCalledWith("构建人类命运共同体");
      expect(apiClient.detectCulturalTerms).toHaveBeenCalledWith({
        text: "构建人类命运共同体",
        cultural_sphere: "western_english",
        audience_type: "general_public",
        genre: "political",
      });
    });

    expect(glossaryState.setDetectedTerms).toHaveBeenCalled();
    expect(glossaryState.setCulturalTerms).toHaveBeenCalled();
    expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("analyzed");
  });

  it("sets stale state when text changes after analyzed", async () => {
    apiClient.detectTerms.mockResolvedValue({ terms: [] });
    apiClient.detectCulturalTerms.mockResolvedValue({ terms: [] });

    const { rerender } = render(<TextEditor />);
    fireEvent.click(screen.getByRole("button", { name: /分析术语与文化负载词/ }));

    await waitFor(() => {
      expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("analyzed");
    });

    // Simulate external text change
    workspaceState.input.text = "构建人类命运共同体和一带一路";
    rerender(<TextEditor />);

    await waitFor(() => {
      expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("stale");
    });
  });

  it("falls back to idle when both detections fail", async () => {
    apiClient.detectTerms.mockRejectedValue(new Error("fail"));
    apiClient.detectCulturalTerms.mockRejectedValue(new Error("fail"));

    render(<TextEditor />);
    fireEvent.click(screen.getByRole("button", { name: /分析术语与文化负载词/ }));

    await waitFor(() => {
      expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("idle");
    });
  });

  it("shows analyzed state when only glossary detection succeeds", async () => {
    apiClient.detectTerms.mockResolvedValue({
      terms: [{ source_term: "一带一路", term_type: "political_discourse", risk_notes: "", translations: {} }],
    });
    apiClient.detectCulturalTerms.mockRejectedValue(new Error("fail"));

    render(<TextEditor />);
    fireEvent.click(screen.getByRole("button", { name: /分析术语与文化负载词/ }));

    await waitFor(() => {
      expect(glossaryState.setCulturalAnalysisState).toHaveBeenCalledWith("analyzed");
    });
  });
});

describe("TextEditor clear highlights", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    glossaryState.detectedTerms = [];
    glossaryState.culturalTerms = [];
    glossaryState.culturalAnalysisState = "idle";
    glossaryState.hoveredTerm = null;
    workspaceState.input.text = "构建人类命运共同体";
    apiClient.detectTerms.mockResolvedValue({ terms: [] });
    apiClient.detectCulturalTerms.mockResolvedValue({ terms: [] });
  });

  it("clear button disabled in idle/loading/empty, enabled with results", () => {
    const { rerender } = render(<TextEditor />);
    // idle → disabled
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeDisabled();

    // analyzed 但无结果 → disabled
    glossaryState.culturalAnalysisState = "analyzed";
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeDisabled();

    // analyzed 且有结果 → enabled
    glossaryState.detectedTerms = [
      { source_term: "人类命运共同体", term_type: "political_discourse", risk_notes: "", translations: {} },
    ];
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeEnabled();

    // stale 且有结果 → 仍可用（文本变更后高亮保留，可清除）
    glossaryState.culturalAnalysisState = "stale";
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeEnabled();

    // loading（即使有结果）→ disabled
    glossaryState.culturalAnalysisState = "loading";
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeDisabled();
  });

  it("clicking clear invokes clearHighlights and resets to idle without re-detecting", () => {
    glossaryState.culturalAnalysisState = "analyzed";
    glossaryState.detectedTerms = [
      { source_term: "人类命运共同体", term_type: "political_discourse", risk_notes: "", translations: {} },
    ];
    glossaryState.culturalTerms = [
      { term: "人类命运共同体", offset: 2, length: 7, culture_gap: "high", adaptation_strategy: "explanatory", suggested_rendering: "x", reason: "r", term_type: "cultural_metaphor" },
    ];

    const { rerender } = render(<TextEditor />);
    const clearBtn = screen.getByRole("button", { name: "清除高亮" });
    fireEvent.click(clearBtn);

    expect(glossaryState.clearHighlights).toHaveBeenCalledTimes(1);
    // 清除不触发检测接口
    expect(apiClient.detectTerms).not.toHaveBeenCalled();
    expect(apiClient.detectCulturalTerms).not.toHaveBeenCalled();

    // mock clearHighlights 已将状态重置为 idle；rerender 后「分析」按钮回到 idle 文案，清除按钮再次禁用
    rerender(<TextEditor />);
    expect(screen.getByRole("button", { name: "分析术语与文化负载词" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "清除高亮" })).toBeDisabled();
  });
});
