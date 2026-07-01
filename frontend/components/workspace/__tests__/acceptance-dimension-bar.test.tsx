import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AcceptanceDimensionBar } from "../acceptance-dimension-bar";

describe("AcceptanceDimensionBar", () => {
  it("renders label and score", () => {
    render(<AcceptanceDimensionBar label="受众匹配度" score={20} />);
    expect(screen.getByText("受众匹配度")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("bar width is proportional to score out of 25", () => {
    const { container } = render(<AcceptanceDimensionBar label="x" score={25} />);
    const bar = container.querySelector("[data-testid='dim-bar-fill']") as HTMLElement;
    expect(bar.style.width).toBe("100%");
  });

  it("score 0 gives 0% width", () => {
    const { container } = render(<AcceptanceDimensionBar label="x" score={0} />);
    const bar = container.querySelector("[data-testid='dim-bar-fill']") as HTMLElement;
    expect(bar.style.width).toBe("0%");
  });
});