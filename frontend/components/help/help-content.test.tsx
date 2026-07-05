import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HelpContent } from "./help-content";

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
});
