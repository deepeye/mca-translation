const SCORE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  excellent: { bg: "#DCFCE7", text: "#166534", label: "优秀" },
  good: { bg: "#DBEAFE", text: "#1E40AF", label: "良好" },
  fair: { bg: "#FEF9C3", text: "#854D0E", label: "一般" },
  poor: { bg: "#FFEDD5", text: "#9A3412", label: "待改进" },
  critical: { bg: "#FEE2E2", text: "#991B1B", label: "需重写" },
};

function getScoreGrade(score: number) {
  if (score >= 90) return "excellent";
  if (score >= 75) return "good";
  if (score >= 60) return "fair";
  if (score >= 40) return "poor";
  return "critical";
}

export function ScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const grade = getScoreGrade(score);
  const style = SCORE_COLORS[grade];

  const sizeClasses = {
    sm: "text-lg w-14 h-14",
    md: "text-2xl w-20 h-20",
    lg: "text-4xl w-28 h-28",
  };

  return (
    <div
      className={`flex flex-col items-center justify-center rounded-full font-bold ${sizeClasses[size]}`}
      style={{ background: style.bg, color: style.text }}
    >
      <span>{score}</span>
      {size !== "sm" && <span className="text-[10px] font-normal">{style.label}</span>}
    </div>
  );
}

export function CategoryScoreBar({ name, score }: { name: string; score: number }) {
  const grade = getScoreGrade(score);
  const style = SCORE_COLORS[grade];

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 shrink-0 text-muted-foreground">{name}</span>
      <div className="h-2 flex-1 rounded-full bg-gray-100">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{ width: `${score}%`, background: style.text }}
        />
      </div>
      <span className="w-8 text-right font-medium" style={{ color: style.text }}>{score}</span>
    </div>
  );
}
