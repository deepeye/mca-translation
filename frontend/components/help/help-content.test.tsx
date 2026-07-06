import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HelpContent } from "./help-content";
import { extractHeadings } from "@/lib/help";

describe("HelpContent", () => {
  it("renders markdown headings and paragraphs", () => {
    render(<HelpContent content={"## 快速开始\n\n欢迎使用。"} />);
    expect(screen.getByRole("heading", { name: "快速开始" })).toBeInTheDocument();
    expect(screen.getByText("欢迎使用。")).toBeInTheDocument();
  });

  it("renders a table", () => {
    render(<HelpContent content={"| A | B |\n|---|---|\n| 1 | 2 |"} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  // 回归：rehype-slug 生成的 id 必须透传到渲染的 h2/h3 上，
  // 否则左侧目录 <a href="#id"> 锚点无法定位（id 被自定义组件丢弃）。
  it("forwards rehype-slug id on h2/h3 so TOC anchor links resolve", () => {
    const md = "## 第 1 章 快速开始\n\n### 1.1 登录与注册\n\n正文。";
    const { container } = render(<HelpContent content={md} />);
    for (const h of extractHeadings(md)) {
      const el = container.querySelector(`#${CSS.escape(h.id)}`);
      expect(el).not.toBeNull();
      expect(el?.tagName).toBe(h.level === 2 ? "H2" : "H3");
    }
  });
});
