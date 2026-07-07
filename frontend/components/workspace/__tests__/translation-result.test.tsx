import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const translationState = vi.hoisted(() => ({
  results: {} as Record<string, any>,
  setResult: vi.fn(),
}));

vi.mock("@/stores/translation-store", () => ({
  useTranslationStore: vi.fn((selector?: (s: any) => any) =>
    selector ? selector(translationState) : translationState,
  ),
}));

vi.mock("../cultural-adaptation-panel", () => ({
  CulturalAdaptationPanel: () => null,
}));
vi.mock("../risk-annotation-popover", () => ({
  RiskAnnotationPopover: ({ children }: any) => <>{children}</>,
}));

import { TranslationResult } from "../translation-result";

const baseResult = {
  riskAnnotations: [],
  acceptanceScore: -1,
  highlightedIndex: null,
  culturalAdaptation: null,
};

describe("TranslationResult streaming cursor", () => {
  it("shows blinking cursor while streaming with text", () => {
    translationState.results = {
      "en-GB": { ...baseResult, status: "streaming", translatedText: "Hello" },
    };
    render(<TranslationResult language="en-GB" />);
    expect(screen.getByText("▍")).toBeInTheDocument();
  });

  it("hides cursor when completed", () => {
    translationState.results = {
      "en-GB": { ...baseResult, status: "completed", translatedText: "Hello world" },
    };
    render(<TranslationResult language="en-GB" />);
    expect(screen.queryByText("▍")).not.toBeInTheDocument();
  });
});
