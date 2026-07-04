import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConsumptionChart } from "../consumption-chart";

describe("ConsumptionChart", () => {
  it("renders one bar per day", () => {
    const data = [
      { date: "2026-07-01", consumed: 10 },
      { date: "2026-07-02", consumed: 0 },
      { date: "2026-07-03", consumed: 30 },
    ];
    const { container } = render(<ConsumptionChart data={data} />);
    // 每个 day 一个 rect
    const rects = container.querySelectorAll("rect");
    expect(rects.length).toBe(3);
  });

  it("scales bar heights to the max consumed", () => {
    const data = [
      { date: "2026-07-01", consumed: 10 },
      { date: "2026-07-02", consumed: 30 },
    ];
    const { container } = render(<ConsumptionChart data={data} />);
    const rects = container.querySelectorAll("rect");
    const heights = Array.from(rects).map((r) => Number(r.getAttribute("height")));
    // 第二根（30）应高于第一根（10）
    expect(heights[1]).toBeGreaterThan(heights[0]);
  });

  it("renders zero-height bar for zero-consumption day", () => {
    const { container } = render(
      <ConsumptionChart data={[{ date: "2026-07-01", consumed: 0 }]} />
    );
    const rect = container.querySelector("rect");
    expect(Number(rect?.getAttribute("height") || -1)).toBe(0);
  });
});
