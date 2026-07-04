import { describe, it, expect, beforeEach } from "vitest";
import { useWorkspaceStore } from "@/stores/workspace-store";

describe("workspace-store language→sphere affinity", () => {
  beforeEach(() => {
    useWorkspaceStore.getState().reset();
  });

  it("fills culturalSphere from language affinity when untouched", () => {
    useWorkspaceStore.getState().setLanguages(["ru-RU"]);
    expect(useWorkspaceStore.getState().input.culturalSphere).toBe("russian_sphere");
  });

  it("does not override sphere after user manually sets it", () => {
    useWorkspaceStore.getState().setCulturalSphere("african");
    useWorkspaceStore.getState().setLanguages(["ru-RU"]);
    expect(useWorkspaceStore.getState().input.culturalSphere).toBe("african");
  });

  it("no-ops for languages with no affinity (th-TH)", () => {
    useWorkspaceStore.getState().setLanguages(["th-TH"]);
    expect(useWorkspaceStore.getState().input.culturalSphere).toBe("western_english");
  });

  it("loadFromHistory marks sphere touched (no re-trigger)", () => {
    useWorkspaceStore.getState().loadFromHistory({
      id: "j1", source_text: "x", genre: "political", strategy: "semantic_equivalence",
      cultural_sphere: "south_asian", audience_type: "media", target_languages: ["hi-IN"],
    });
    useWorkspaceStore.getState().setLanguages(["ru-RU"]);
    expect(useWorkspaceStore.getState().input.culturalSphere).toBe("south_asian");
  });
});

describe("workspace-store activeLanguage", () => {
  beforeEach(() => {
    useWorkspaceStore.getState().reset();
  });

  it("defaults activeLanguage to en-GB on reset", () => {
    // Given default state
    expect(useWorkspaceStore.getState().activeLanguage).toBe("en-GB");
    // And after explicit reset
    useWorkspaceStore.getState().reset();
    expect(useWorkspaceStore.getState().activeLanguage).toBe("en-GB");
  });

  it("setActiveLanguage updates activeLanguage directly", () => {
    useWorkspaceStore.getState().setActiveLanguage("zh-CN");
    expect(useWorkspaceStore.getState().activeLanguage).toBe("zh-CN");
  });

  it("setLanguages keeps activeLanguage if it is among the new set", () => {
    useWorkspaceStore.getState().setActiveLanguage("fr-FR");
    useWorkspaceStore.getState().setLanguages(["fr-FR", "de-DE", "ja-JP"]);
    expect(useWorkspaceStore.getState().activeLanguage).toBe("fr-FR");
  });

  it("setLanguages falls back to first language when current activeLanguage disappears", () => {
    useWorkspaceStore.getState().setActiveLanguage("fr-FR");
    useWorkspaceStore.getState().setLanguages(["de-DE", "ja-JP"]);
    expect(useWorkspaceStore.getState().activeLanguage).toBe("de-DE");
  });

  it("setLanguages falls back to en-GB when languages array is empty", () => {
    useWorkspaceStore.getState().setActiveLanguage("fr-FR");
    useWorkspaceStore.getState().setLanguages([]);
    expect(useWorkspaceStore.getState().activeLanguage).toBe("en-GB");
  });

  it("loadFromHistory sets activeLanguage from target_languages[0]", () => {
    useWorkspaceStore.getState().loadFromHistory({
      id: "j2", source_text: "hello", genre: "news", strategy: "audience_first",
      cultural_sphere: "western_english", audience_type: "media",
      target_languages: ["zh-CN", "ja-JP", "ko-KR"],
    });
    expect(useWorkspaceStore.getState().activeLanguage).toBe("zh-CN");
  });

  it("loadFromHistory falls back to en-GB when target_languages is empty", () => {
    useWorkspaceStore.getState().loadFromHistory({
      id: "j3", source_text: "hello", genre: "news", strategy: "audience_first",
      cultural_sphere: "western_english", audience_type: "media",
      target_languages: [],
    });
    expect(useWorkspaceStore.getState().activeLanguage).toBe("en-GB");
  });
});
