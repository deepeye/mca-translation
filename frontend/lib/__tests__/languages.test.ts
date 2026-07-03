import { describe, it, expect } from "vitest";
import { LANGUAGES, LANGUAGE_LABELS, affinitySphereFor } from "@/lib/languages";

describe("languages mirror", () => {
  it("has 18 languages", () => {
    expect(LANGUAGES).toHaveLength(18);
  });

  it("LANGUAGE_LABELS covers all codes", () => {
    for (const l of LANGUAGES) {
      expect(LANGUAGE_LABELS[l.code]).toBe(l.labelZh);
    }
  });

  it("affinitySphereFor returns expected spheres", () => {
    expect(affinitySphereFor("ru-RU")).toBe("russian_sphere");
    expect(affinitySphereFor("ar")).toBe("islamic_middle_east");
    expect(affinitySphereFor("th-TH")).toBeNull();
  });
});
