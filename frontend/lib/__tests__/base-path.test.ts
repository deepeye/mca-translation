import { describe, it, expect, vi, beforeEach } from "vitest";

describe("base-path", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  it("BASE_PATH reflects NEXT_PUBLIC_BASE_PATH when set", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/mca");
    const { BASE_PATH } = await import("@/lib/base-path");
    expect(BASE_PATH).toBe("/mca");
  });

  it("BASE_PATH is empty string when NEXT_PUBLIC_BASE_PATH unset", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "");
    const { BASE_PATH } = await import("@/lib/base-path");
    expect(BASE_PATH).toBe("");
  });

  it("loginPath prefixes basePath explicitly", async () => {
    const { loginPath } = await import("@/lib/base-path");
    expect(loginPath("/mca")).toBe("/mca/login");
    expect(loginPath("")).toBe("/login");
  });

  it("loginPath defaults to BASE_PATH", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/mca");
    const { loginPath } = await import("@/lib/base-path");
    expect(loginPath()).toBe("/mca/login");
  });
});
