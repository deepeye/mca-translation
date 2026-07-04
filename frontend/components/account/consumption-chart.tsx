"use client";

import { DailyConsumption } from "@/lib/credits-api";

const WIDTH = 600;
const HEIGHT = 160;
const BAR_GAP = 2;

export function ConsumptionChart({ data }: { data: DailyConsumption[] }) {
  const max = Math.max(1, ...data.map((d) => d.consumed));
  const barWidth = data.length > 0 ? (WIDTH - BAR_GAP * (data.length - 1)) / data.length : 0;

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full h-40" role="img" aria-label="消费趋势">
      {data.map((d, i) => {
        const h = (d.consumed / max) * (HEIGHT - 20);
        const x = i * (barWidth + BAR_GAP);
        const y = HEIGHT - h;
        return (
          <g key={d.date}>
            <rect x={x} y={y} width={barWidth} height={h} fill="#2a9d8f" />
            <title>{`${d.date}: ${d.consumed} 信用分`}</title>
          </g>
        );
      })}
    </svg>
  );
}
