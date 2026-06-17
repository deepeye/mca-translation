"use client";

import { Genre, useWorkspaceStore } from "@/stores/workspace-store";
import { getDisabledGenres } from "@/lib/translation-conflicts";

const GENRES: { value: Genre; label: string }[] = [
  { value: "political", label: "政治话语" },
  { value: "news", label: "新闻稿" },
  { value: "policy", label: "政策文件" },
  { value: "brand", label: "品牌传播" },
];

export function GenreSelector() {
  const genre = useWorkspaceStore((s) => s.input.genre);
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const setGenre = useWorkspaceStore((s) => s.setGenre);
  const disabledGenres = getDisabledGenres(strategy);

  return (
    <div className="flex gap-1.5">
      {GENRES.map((g) => {
        const disabled = disabledGenres.includes(g.value);
        return (
          <button
            key={g.value}
            onClick={() => { if (!disabled) setGenre(g.value); }}
            disabled={disabled}
            title={disabled ? "与当前翻译策略（直译参考）冲突，不可选" : undefined}
            className={`rounded px-2.5 py-1 text-xs transition-all duration-200 border-l-2 ${
              disabled
                ? "opacity-50 cursor-not-allowed bg-muted text-muted-foreground border-l-transparent"
                : genre === g.value
                  ? "cursor-pointer active:scale-[0.95] bg-teal-lightest text-teal border-l-teal font-medium"
                  : "cursor-pointer active:scale-[0.95] bg-muted text-muted-foreground border-l-transparent hover:bg-teal-lightest hover:text-foreground"
            }`}
          >
            {g.label}
          </button>
        );
      })}
    </div>
  );
}
