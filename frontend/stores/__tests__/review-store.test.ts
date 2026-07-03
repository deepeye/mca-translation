import { describe, it, expect, beforeEach } from "vitest";
import { useReviewStore } from "@/stores/review-store";

describe("review-store language→sphere affinity", () => {
  beforeEach(() => {
    useReviewStore.getState().reset();
  });

  it("fills culturalSphere from language affinity when untouched", () => {
    useReviewStore.getState().setTargetLanguage("ar");
    expect(useReviewStore.getState().culturalSphere).toBe("islamic_middle_east");
  });

  it("does not override sphere after manual set", () => {
    useReviewStore.getState().setCulturalSphere("african");
    useReviewStore.getState().setTargetLanguage("ar");
    expect(useReviewStore.getState().culturalSphere).toBe("african");
  });

  it("no-ops for language with no affinity", () => {
    useReviewStore.getState().setTargetLanguage("ms-MY");
    expect(useReviewStore.getState().culturalSphere).toBe("western_english");
  });
});
