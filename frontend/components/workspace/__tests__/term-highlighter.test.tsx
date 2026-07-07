import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Reactive mock state — listeners allow setHoveredTerm to trigger re-renders,
// 模拟 Zustand store 的订阅机制，使 hover 状态变更能驱动组件重渲染。
const glossaryState = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  return {
    detectedTerms: [] as any[],
    hoveredTerm: null as string | null,
    listeners,
    setHoveredTerm: vi.fn((term: string | null) => {
      glossaryState.hoveredTerm = term;
      glossaryState.listeners.forEach((l) => l());
    }),
  };
});

const workspaceState = vi.hoisted(() => ({
  activeLanguage: "en-GB",
}));

vi.mock("@/stores/glossary-store", async () => {
  const { useSyncExternalStore } = await import("react");
  return {
    useGlossaryStore: vi.fn((selector?: (s: unknown) => unknown) => {
      // useSyncExternalStore 订阅 listeners，当 hoveredTerm 变化时触发重渲染
      useSyncExternalStore(
        (cb: () => void) => {
          glossaryState.listeners.add(cb);
          return () => {
            glossaryState.listeners.delete(cb);
          };
        },
        () => glossaryState.hoveredTerm,
      );
      return selector ? selector(glossaryState) : glossaryState;
    }),
  };
});

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector?: (s: unknown) => unknown) =>
    selector ? selector(workspaceState) : workspaceState,
  ),
}));

import { TermHighlighter } from "../term-highlighter";

describe("TermHighlighter", () => {
  beforeEach(() => {
    glossaryState.detectedTerms = [];
    glossaryState.hoveredTerm = null;
    workspaceState.activeLanguage = "en-GB";
  });

  it("renders nothing when no terms detected", () => {
    const { container } = render(<TermHighlighter />);
    expect(container.firstChild).toBeNull();
  });

  it("renders badge for each detected term", () => {
    glossaryState.detectedTerms = [
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险政治话语",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
        },
      },
    ];
    render(<TermHighlighter />);
    expect(screen.getByText("一带一路")).toBeInTheDocument();
  });

  it("shows hover tooltip with preferred translation", () => {
    glossaryState.detectedTerms = [
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
        },
      },
    ];
    render(<TermHighlighter />);
    fireEvent.mouseEnter(screen.getByText("一带一路"));
    expect(screen.getByText(/英语/)).toBeInTheDocument();
    expect(screen.getByText(/BRI/)).toBeInTheDocument();
  });
});
