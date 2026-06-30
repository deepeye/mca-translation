"use client";

import { useCallback } from "react";

export interface FilterValues {
  genre?: string;
  status?: string;
}

interface FilterBarProps {
  values: FilterValues;
  onChange: (filters: FilterValues) => void;
}

const GENRE_OPTIONS = [
  { value: "", label: "全部文体" },
  { value: "political", label: "政治" },
  { value: "news", label: "新闻" },
  { value: "policy", label: "政策" },
  { value: "brand", label: "品牌" },
];

const STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "processing", label: "进行中" },
];

export function FilterBar({ values, onChange }: FilterBarProps) {
  const handleGenreChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onChange({ ...values, genre: e.target.value || undefined });
    },
    [values, onChange],
  );

  const handleStatusChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onChange({ ...values, status: e.target.value || undefined });
    },
    [values, onChange],
  );

  return (
    <div className="flex gap-2 px-1">
      <select
        className="flex h-9 w-36 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        value={values.genre || ""}
        onChange={handleGenreChange}
      >
        {GENRE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <select
        className="flex h-9 w-36 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        value={values.status || ""}
        onChange={handleStatusChange}
      >
        {STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
