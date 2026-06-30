"use client";

export interface JobListItemData {
  id: string;
  status: string;
  genre: string;
  target_languages: string[];
  source_text: string | null;
  created_at: string;
}

interface TaskCardProps {
  job: JobListItemData;
  isSelected: boolean;
  onClick: () => void;
}

const STATUS_CONFIG: Record<string, { icon: string; label: string }> = {
  completed: { icon: "✓", label: "已完成" },
  failed: { icon: "✗", label: "失败" },
  processing: { icon: "⟳", label: "进行中" },
  pending: { icon: "⟳", label: "等待中" },
  partial: { icon: "⚠", label: "部分完成" },
};

const GENRE_LABELS: Record<string, string> = {
  political: "政治",
  news: "新闻",
  policy: "政策",
  brand: "品牌",
};

export function TaskCard({ job, isSelected, onClick }: TaskCardProps) {
  const statusCfg = STATUS_CONFIG[job.status] || { icon: "?", label: job.status };
  const genreLabel = GENRE_LABELS[job.genre] || job.genre;
  const excerpt = job.source_text
    ? job.source_text.length > 80
      ? job.source_text.slice(0, 80) + "..."
      : job.source_text
    : "";
  const time = new Date(job.created_at).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <button
      onClick={onClick}
      className={`w-full cursor-pointer rounded-lg border p-3 text-left transition-all duration-150 active:scale-[0.99] ${
        isSelected
          ? "border-teal bg-teal-lightest/50 shadow-sm"
          : "border-border bg-card hover:border-teal-light hover:shadow-sm"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm" title={statusCfg.label}>
          {statusCfg.icon}
        </span>
        <span className="rounded bg-teal-lightest px-1.5 py-0.5 text-xs font-medium text-teal-dark">
          {genreLabel}
        </span>
        <div className="flex flex-wrap gap-1">
          {job.target_languages.map((lang) => (
            <span
              key={lang}
              className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
            >
              {lang}
            </span>
          ))}
        </div>
      </div>
      {excerpt && (
        <p className="mt-1.5 text-xs text-muted-foreground line-clamp-2">{excerpt}</p>
      )}
      <p className="mt-1 text-[11px] text-muted-foreground/60">{time}</p>
    </button>
  );
}
