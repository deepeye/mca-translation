"use client";

import { useEffect, useRef, useCallback } from "react";
import { useGlossaryStore } from "@/stores/glossary-store";
import { apiClient } from "@/lib/api-client";

interface TermHighlighterProps {
  text: string;
  containerClassName?: string;
}

export function TermHighlighter({ text, containerClassName = "" }: TermHighlighterProps) {
  const detectedTerms = useGlossaryStore((s) => s.detectedTerms);
  const setDetectedTerms = useGlossaryStore((s) => s.setDetectedTerms);
  const setIsLoading = useGlossaryStore((s) => s.setIsLoading);
  const hoveredTerm = useGlossaryStore((s) => s.hoveredTerm);
  const setHoveredTerm = useGlossaryStore((s) => s.setHoveredTerm);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const detect = useCallback(
    async (value: string) => {
      if (!value.trim()) {
        setDetectedTerms([]);
        return;
      }
      setIsLoading(true);
      try {
        const data = await apiClient.detectTerms(value);
        setDetectedTerms(data.terms || []);
      } catch {
        setDetectedTerms([]);
      } finally {
        setIsLoading(false);
      }
    },
    [setDetectedTerms, setIsLoading]
  );

  useEffect(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => detect(text), 800);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [text, detect]);

  if (detectedTerms.length === 0) return null;

  return (
    <div className={`flex flex-wrap gap-1.5 ${containerClassName}`}>
      {detectedTerms.map((term) => (
        <div
          key={term.source_term}
          className="relative"
          onMouseEnter={() => setHoveredTerm(term.source_term)}
          onMouseLeave={() => setHoveredTerm(null)}
        >
          <span
            className={`inline-flex cursor-default items-center rounded px-1.5 py-0.5 text-xs font-medium transition-colors ${
              term.term_type === "political_discourse"
                ? "bg-blue-100 text-blue-700"
                : "bg-orange-100 text-orange-700"
            }`}
          >
            {term.source_term}
          </span>
          {hoveredTerm === term.source_term && (
            <div className="absolute bottom-full left-0 z-50 mb-1 w-64 rounded-md border border-border bg-white p-2 shadow-lg">
              <div className="text-xs font-semibold text-foreground">{term.source_term}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {term.term_type === "political_discourse" ? "政治话语" : "文化隐喻"}
              </div>
              {term.risk_notes && (
                <div className="mt-1 text-xs text-orange-600">⚠ {term.risk_notes}</div>
              )}
              {term.translations["en-GB"] && (
                <div className="mt-1 text-xs text-teal-700">
                  英语：{term.translations["en-GB"].preferred}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
