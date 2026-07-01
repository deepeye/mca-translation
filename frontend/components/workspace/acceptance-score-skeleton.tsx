// 评分加载骨架（首次评分 / 受众切换时）。

export function AcceptanceScoreSkeleton() {
  return (
    <div className="space-y-3 px-3 pb-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="space-y-2">
          <div className="h-4 w-32 animate-pulse rounded bg-muted" />
          <div className="h-3 w-full animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}