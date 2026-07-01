// frontend/components/workspace/__tests__/decision-log-panel.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DecisionLogPanel } from "../decision-log-panel";

// Mock stores
// NOTE: 组件使用 zustand 选择器写法 useTranslationStore((s) => s.x)，
// 因此 mock 需以 state 对象调用选择器，否则会返回整个 store 对象导致解构失败。
// 数据值与 task brief 保持一致。
vi.mock("@/stores/translation-store", () => ({
  useTranslationStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector({
      results: { "en-GB": { resultId: "res-1", status: "completed" } },
      decisionLogs: [],
      isLoadingDecisions: false,
      loadDecisionLogs: vi.fn(),
      clearDecisionLogs: vi.fn(),
    }),
  ),
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector({
      languages: ["en-GB"],
      currentJobId: "job-1",
    }),
  ),
}));

describe("DecisionLogPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders collapsed by default", () => {
    render(<DecisionLogPanel />);
    expect(screen.getByText("决策日志")).toBeInTheDocument();
    // 面板默认折叠，不显示空状态文案
    expect(screen.queryByText("本次翻译无关键决策记录")).not.toBeInTheDocument();
  });

  it("shows empty state when expanded with no logs", () => {
    render(<DecisionLogPanel />);
    fireEvent.click(screen.getByText("决策日志"));
    expect(screen.getByText("本次翻译无关键决策记录")).toBeInTheDocument();
  });
});
