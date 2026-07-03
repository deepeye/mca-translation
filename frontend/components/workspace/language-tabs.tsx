"use client";

import { useWorkspaceStore } from "@/stores/workspace-store";
import { LANGUAGE_LABELS } from "@/lib/languages";

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
