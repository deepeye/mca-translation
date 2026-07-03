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
