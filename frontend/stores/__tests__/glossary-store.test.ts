import { describe, it, expect, beforeEach } from "vitest";
import { useGlossaryStore } from "@/stores/glossary-store";
import type { DetectedTerm } from "@/stores/glossary-store";
import type { CulturalTermResult } from "@/lib/api-client";

// 已分析后的非空状态样本 — 用于验证 clearHighlights 将其全部重置
const seededGlossaryTerm: DetectedTerm = {
  source_term: "人类命运共同体",
  term_type: "political_discourse",
  risk_notes: "高风险",
  translations: {},
};

const seededCulturalTerm: CulturalTermResult = {
  term: "命运共同体",
  offset: 2,
  length: 5,
  culture_gap: "high",
  adaptation_strategy: "explanatory",
  suggested_rendering: "a community of shared future",
  reason: "政治话语",
  term_type: "cultural_metaphor",
};

describe("glossary-store clearHighlights", () => {
  beforeEach(() => {
    useGlossaryStore.setState({
      detectedTerms: [seededGlossaryTerm],
      culturalTerms: [seededCulturalTerm],
      culturalAnalysisState: "analyzed",
      hoveredTerm: "人类命运共同体",
    });
  });

  it("resets all highlight-related fields to defaults", () => {
    useGlossaryStore.getState().clearHighlights();
    const s = useGlossaryStore.getState();
    expect(s.detectedTerms).toEqual([]);
    expect(s.culturalTerms).toEqual([]);
    expect(s.culturalAnalysisState).toBe("idle");
    expect(s.hoveredTerm).toBeNull();
  });
});
