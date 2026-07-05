import { describe, it, expect } from "vitest";
import { transformImagePaths, extractHeadings } from "./help";

describe("transformImagePaths", () => {
  it("replaces ./help/ with /help/", () => {
    const input = "![工作台](./help/workspace-overview.svg)";
    expect(transformImagePaths(input)).toBe("![工作台](/help/workspace-overview.svg)");
  });

  it("leaves other paths unchanged", () => {
    const input = "![其他](/other/image.png)";
    expect(transformImagePaths(input)).toBe("![其他](/other/image.png)");
  });
});

describe("extractHeadings", () => {
  it("extracts h2 and h3 with github-compatible ids", () => {
    const input = `## 快速开始\n### 登录\n## 术语库`;
    const headings = extractHeadings(input);
    expect(headings).toEqual([
      { level: 2, text: "快速开始", id: "快速开始" },
      { level: 3, text: "登录", id: "登录" },
      { level: 2, text: "术语库", id: "术语库" },
    ]);
  });

  it("generates unique ids for duplicate headings", () => {
    const input = `## 登录\n### 登录`;
    const headings = extractHeadings(input);
    expect(headings[0].id).toBe("登录");
    expect(headings[1].id).toBe("登录-1");
  });

  it("handles punctuation and spaces", () => {
    const input = `## 接受 / 忽略 / 回退操作`;
    const headings = extractHeadings(input);
    expect(headings[0].id).toBe("接受--忽略--回退操作");
  });
});
