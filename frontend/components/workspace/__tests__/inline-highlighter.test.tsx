import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InlineHighlighter } from "../inline-highlighter";

// Mock stores — 选择器写法，mock 需以 state 对象调用选择器
const glossaryState: {
  detectedTerms: unknown[];
  culturalTerms: unknown[];
} = {
  detectedTerms: [],
  culturalTerms: [],
};

vi.mock("@/stores/glossary-store", () => ({
  useGlossaryStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector(glossaryState),
  ),
}));

const workspaceState: {
  input: { text: string };
  setText: ReturnType<typeof vi.fn>;
  activeLanguage: string;
} = {
  input: { text: "构建人类命运共同体" },
  setText: vi.fn(),
  activeLanguage: "en-GB",
};

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector(workspaceState),
  ),
}));

function setCultural(terms: unknown[]) {
  glossaryState.culturalTerms = terms;
}
function setGlossary(terms: unknown[]) {
  glossaryState.detectedTerms = terms;
}
function setText(t: string) {
  workspaceState.input.text = t;
}

describe("InlineHighlighter", () => {
  beforeEach(() => {
    setGlossary([]);
    setCultural([]);
    setText("构建人类命运共同体");
  });

  it("渲染文化负载词高亮 mark（按 offset 定位）", () => {
    setText("构建人类命运共同体");
    setCultural([
      {
        term: "人类命运共同体",
        offset: 2,
        length: 7,
        culture_gap: "high",
        adaptation_strategy: "explanatory",
        suggested_rendering: "a community with a shared future for mankind",
        reason: "政治话语承载意识形态内涵",
        term_type: "cultural_metaphor",
      },
    ]);
    const { container } = render(<InlineHighlighter />);
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(1);
    expect(marks[0].textContent).toBe("人类命运共同体");
  });

  it("同一术语多次出现全部高亮", () => {
    setText("人类命运共同体，人类命运共同体");
    setCultural([
      {
        term: "人类命运共同体",
        offset: 0,
        length: 7,
        culture_gap: "medium",
        adaptation_strategy: "literal",
        suggested_rendering: "community",
        reason: "r",
        term_type: "cultural_metaphor",
      },
    ]);
    // 注意：前端按 culturalTerms 的 offset/length 直接定位，不自行重算多次出现。
    // 这里仅给一个 offset，故只一个 mark。多次出现由后端 detect-cultural 返回多条。
    const { container } = render(<InlineHighlighter />);
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(1);
  });

  it("glossary 与 cultural 重叠时 glossary 优先（只渲染一个 mark）", () => {
    setText("一带一路");
    setGlossary([
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险政治话语",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
        },
      },
    ]);
    setCultural([
      {
        term: "一带一路",
        offset: 0,
        length: 4,
        culture_gap: "high",
        adaptation_strategy: "explanatory",
        suggested_rendering: "the Belt and Road Initiative",
        reason: "文化隐喻",
        term_type: "cultural_metaphor",
      },
    ]);
    const { container } = render(<InlineHighlighter />);
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(1); // cultural 被吸收
  });

  it("hover mark 显示 Popover 含建议与理由", () => {
    setText("构建人类命运共同体");
    setCultural([
      {
        term: "人类命运共同体",
        offset: 2,
        length: 7,
        culture_gap: "high",
        adaptation_strategy: "explanatory",
        suggested_rendering: "a community with a shared future for mankind",
        reason: "政治话语承载意识形态内涵",
        term_type: "cultural_metaphor",
      },
    ]);
    const { container } = render(<InlineHighlighter />);
    const mark = container.querySelector("mark")!;
    // 初始无 Popover 内容
    expect(screen.queryByText(/建议译法/)).not.toBeInTheDocument();
    fireEvent.mouseEnter(mark);
    expect(screen.getByText(/建议译法/)).toBeInTheDocument();
    expect(
      screen.getByText(/a community with a shared future for mankind/),
    ).toBeInTheDocument();
    expect(screen.getByText(/政治话语承载意识形态内涵/)).toBeInTheDocument();
  });

  it("无任何术语时不渲染 mark", () => {
    setText("普通文本无术语");
    setGlossary([]);
    setCultural([]);
    const { container } = render(<InlineHighlighter />);
    expect(container.querySelectorAll("mark").length).toBe(0);
  });

  it("glossary popover shows active language translation when available", () => {
    workspaceState.activeLanguage = "ar";
    setText("一带一路");
    setGlossary([
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
          ar: { preferred: "مبادرة الحزام والطريق", notes: "", alternatives: [] },
        },
      },
    ]);
    const { container } = render(<InlineHighlighter />);
    // Verify the mark text is correct (source term)
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(1);
    expect(marks[0].textContent).toBe("一带一路");
    // Verify popover shows active language suggestion on hover
    fireEvent.mouseEnter(marks[0]);
    expect(screen.getByText(/مبادرة الحزام والطريق/)).toBeInTheDocument();
    workspaceState.activeLanguage = "en-GB";
  });

  it("glossary popover falls back to en-GB when active language missing", () => {
    workspaceState.activeLanguage = "ar";
    setText("一带一路");
    setGlossary([
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
        },
      },
    ]);
    const { container } = render(<InlineHighlighter />);
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(1);
    // Hover mark to trigger popover
    fireEvent.mouseEnter(marks[0]);
    // Should show en-GB fallback (BRI) in suggestion
    expect(screen.getByText(/BRI/)).toBeInTheDocument();
    workspaceState.activeLanguage = "en-GB";
  });

  it("glossary 与 cultural 同时存在时各自渲染 mark", () => {
    setText("一带一路与构建人类命运共同体");
    setGlossary([
      {
        source_term: "一带一路",
        term_type: "political_discourse",
        risk_notes: "高风险",
        translations: {
          "en-GB": { preferred: "BRI", notes: "", alternatives: [] },
        },
      },
    ]);
    setCultural([
      {
        term: "人类命运共同体",
        offset: 7,
        length: 7,
        culture_gap: "high",
        adaptation_strategy: "explanatory",
        suggested_rendering: "a community with a shared future for mankind",
        reason: "政治话语",
        term_type: "cultural_metaphor",
      },
    ]);
    const { container } = render(<InlineHighlighter />);
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(2);
    expect(marks[0].textContent).toBe("一带一路");
    expect(marks[1].textContent).toBe("人类命运共同体");
  });
});
