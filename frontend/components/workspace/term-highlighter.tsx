"use client";

import { useGlossaryStore } from "@/stores/glossary-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { LANGUAGE_LABELS } from "@/lib/languages";
import {
  DEFAULT_TERM_TYPE_BADGE_CLASS,
  DEFAULT_TERM_TYPE_LABEL,
  SYSTEM_GLOSSARY_TERM_TYPE_LABELS,
  TERM_TYPE_BADGE_CLASS,
} from "@/lib/glossary-categories";

interface TermHighlighterProps {
  containerClassName?: string;
}

export function TermHighlighter({ containerClassName = "" }: TermHighlighterProps) {
  const detectedTerms = useGlossaryStore((s) => s.detectedTerms);
  const hoveredTerm = useGlossaryStore((s) => s.hoveredTerm);
  const setHoveredTerm = useGlossaryStore((s) => s.setHoveredTerm);
  const activeLang = useWorkspaceStore((s) => s.activeLanguage);

  if (detectedTerms.length === 0) return null;

  return (
    <div className={`flex flex-wrap gap-1.5 ${containerClassName}`}>
      {detectedTerms.map((term) => {
        const badgeClass = TERM_TYPE_BADGE_CLASS[term.term_type] || DEFAULT_TERM_TYPE_BADGE_CLASS;
        const label = SYSTEM_GLOSSARY_TERM_TYPE_LABELS[term.term_type] || DEFAULT_TERM_TYPE_LABEL;
        return (
          <div
            key={term.source_term}
            className="relative"
            onMouseEnter={() => setHoveredTerm(term.source_term)}
            onMouseLeave={() => setHoveredTerm(null)}
          >
            <span
              className={`inline-flex cursor-default items-center rounded px-1.5 py-0.5 text-xs font-medium transition-colors ${badgeClass}`}
            >
              {term.source_term}
            </span>
            {hoveredTerm === term.source_term && (
              <div className="absolute bottom-full left-0 z-50 mb-1 w-64 rounded-md border border-border bg-white p-2 shadow-lg">
                <div className="text-xs font-semibold text-foreground">{term.source_term}</div>
                <div className="mt-1 text-xs text-muted-foreground">{label}</div>
                {term.risk_notes && (
                  <div className="mt-1 text-xs text-orange-600">⚠ {term.risk_notes}</div>
                )}
                {(() => {
                  const translation = term.translations[activeLang] ?? term.translations["en-GB"];
                  const labelCode = term.translations[activeLang] ? activeLang : "en-GB";
                  if (translation) {
                    return (
                      <div className="mt-1 text-xs text-teal-700">
                        {LANGUAGE_LABELS[labelCode] ?? "英语"}：{translation.preferred}
                      </div>
                    );
                  }
                  return null;
                })()}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
