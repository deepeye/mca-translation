"use client";

import { useWorkspaceStore } from "@/stores/workspace-store";

const LANGUAGE_LABELS: Record<string, string> = {
  "en-GB": "英语(英)", "de-DE": "德语", "ja-JP": "日语", "es-ES": "西班牙语", "fr-FR": "法语",
};

export function LanguageTabs({ activeLang, onSwitch }: { activeLang: string; onSwitch: (lang: string) => void }) {
  const languages = useWorkspaceStore((s) => s.languages);

  return (
    <div className="flex gap-1.5">
      {languages.map((code) => (
        <button
          key={code}
          onClick={() => onSwitch(code)}
          className={`cursor-pointer rounded px-2.5 py-1 text-xs transition-all duration-200 active:scale-[0.95] ${
            activeLang === code ? "bg-teal text-white" : "bg-muted text-muted-foreground hover:bg-teal-lightest"
          }`}
        >
          {LANGUAGE_LABELS[code] || code}
        </button>
      ))}
    </div>
  );
}
