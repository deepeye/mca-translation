// 单条四维评分条：0-25 分，宽度按 score/25 比例。

const TEAL = "#0D9488";

export function AcceptanceDimensionBar({ label, score }: { label: string; score: number }) {
  const pct = Math.max(0, Math.min(100, (score / 25) * 100));
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 shrink-0 text-muted-foreground">{label}</span>
      <div className="h-2 flex-1 rounded-full bg-muted">
        <div
          data-testid="dim-bar-fill"
          className="h-2 rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: TEAL }}
        />
      </div>
      <span className="w-6 text-right font-medium" style={{ color: TEAL }}>{Math.round(score)}</span>
    </div>
  );
}