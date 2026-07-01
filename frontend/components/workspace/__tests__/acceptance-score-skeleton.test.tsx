import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { AcceptanceScoreSkeleton } from "../acceptance-score-skeleton";

describe("AcceptanceScoreSkeleton", () => {
  it("renders 3 pulse rows", () => {
    const { container } = render(<AcceptanceScoreSkeleton />);
    const rows = container.querySelectorAll(".animate-pulse");
    expect(rows.length).toBeGreaterThanOrEqual(3);
  });
});