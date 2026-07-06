import { describe, it, expect } from "vitest";
import { buildWsBase } from "@/lib/ws-client";

describe("buildWsBase", () => {
  it("returns wsUrl override when provided (dev direct backend)", () => {
    expect(buildWsBase("ws://localhost:8000", "https:", "airoute.hubpd.com", "/mca"))
      .toBe("ws://localhost:8000");
  });

  it("derives wss:// + basePath on HTTPS page (prod)", () => {
    expect(buildWsBase(undefined, "https:", "airoute.hubpd.com", "/mca"))
      .toBe("wss://airoute.hubpd.com/mca");
  });

  it("derives ws:// + basePath on HTTP page (LAN direct)", () => {
    expect(buildWsBase(undefined, "http:", "10.19.1.95:8082", "/mca"))
      .toBe("ws://10.19.1.95:8082/mca");
  });

  it("works without prefix (basePath empty)", () => {
    expect(buildWsBase(undefined, "http:", "localhost", "")).toBe("ws://localhost");
  });

  it("returns empty string when protocol/host missing (SSR, no window)", () => {
    expect(buildWsBase(undefined, "", "", "/mca")).toBe("");
  });
});
