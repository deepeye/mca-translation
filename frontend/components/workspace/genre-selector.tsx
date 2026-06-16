"use client";

import { Genre, useWorkspaceStore } from "@/stores/workspace-store";

const GENRES: { value: Genre; label: string }[] = [
  { value: "political", label: "政治话语" },
  { value: "news", label: "新闻稿" },
  { value: "policy", label: "政策文件" },
  { value: "brand", label: "品牌传播" },
];

export function GenreSelector() {
  const genre = useWorkspaceStore((s) => s.input.genre);
  const setGenre = useWorkspaceStore((s) => s.setGenre);

  return (
    <div className="flex gap-1.5">
      {GENRES.map((g) => (
        <button
          key={g.value}
          onClick={() => setGenre(g.value)}
          className={`cursor-pointer rounded px-2.5 py-1 text-xs transition-colors ${
            genre === g.value ? "bg-teal text-white" : "bg-muted text-muted-foreground hover:bg-teal-lightest"
          }`}
        >
          {g.label}
        </button>
      ))}
    </div>
  );
}
