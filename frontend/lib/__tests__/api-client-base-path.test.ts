import { describe, it, expect, vi, beforeEach } from "vitest";

// jsdom 不支持真正导航,用 setter spy 捕获 window.location.href 赋值
function mockLocationHref() {
  const hrefSetter = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      set href(v: string) { hrefSetter(v); },
      get href(): string { return ""; },
      assign: hrefSetter,
      replace: hrefSetter,
    } as unknown as Location,
  });
  return hrefSetter;
}

describe("api-client base path wiring", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv("NEXT_PUBLIC_API_URL", ""); // 确保不被绝对地址覆盖
    localStorage.clear();
  });

  it("prefixes fetch URL with BASE_PATH", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/mca");
    const hrefSetter = mockLocationHref();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiClient } = await import("@/lib/api-client");
    await apiClient.listJobs();

    expect(fetchMock).toHaveBeenCalledWith(
      "/mca/api/jobs",
      expect.objectContaining({ method: "GET" }),
    );
    expect(hrefSetter).not.toHaveBeenCalled();
  });

  it("redirects to /mca/login on 401", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/mca");
    const hrefSetter = mockLocationHref();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "unauth" }), { status: 401 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiClient } = await import("@/lib/api-client");
    await expect(apiClient.listJobs()).rejects.toThrow("Unauthorized");

    expect(hrefSetter).toHaveBeenCalledWith("/mca/login");
  });
});
