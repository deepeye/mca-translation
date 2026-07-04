"use client";

import { useMemo, useRef, useCallback } from "react";
import { useGlossaryStore } from "@/stores/glossary-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  CULTURAL_HIGHLIGHT_CLASS,
  CULTURAL_TERM_LABEL,
  DEFAULT_TERM_TYPE_BADGE_CLASS,
  DEFAULT_TERM_TYPE_LABEL,
  SYSTEM_GLOSSARY_TERM_TYPE_LABELS,
  TERM_TYPE_BADGE_CLASS,
} from "@/lib/glossary-categories";

// 统一高亮区间 — 术语库命中(source=glossary)与 LLM 文化负载词(source=cultural)共用
interface HighlightSpan {
  start: number;
  end: number;
  text: string;
  source: "glossary" | "cultural";
  term_type: string;
  label: string;
  risk_notes?: string;
  suggestion?: string; // 转译建议（glossary: en-GB preferred; cultural: suggested_rendering）
  reason?: string;
  culture_gap?: "low" | "medium" | "high";
}

// textarea 与镜像 div 共享的字体度量类 — 必须严格 1:1 否则高亮错位
const MIRROR_TEXT_CLASS =
  "text-sm leading-6 p-3 whitespace-pre-wrap break-words font-sans";

// 在原文中查找 needle 的全部出现位置（首字符偏移）
function findAllOccurrences(text: string, needle: string): number[] {
  if (!needle) return [];
  const offsets: number[] = [];
  let start = 0;
  while (true) {
    const idx = text.indexOf(needle, start);
    if (idx === -1) break;
    offsets.push(idx);
    start = idx + needle.length;
  }
  return offsets;
}

// 合并 glossary 与 cultural 区间，重叠时 glossary 优先（cultural 被吸收）
function buildSpans(
  text: string,
  glossary: {
    source_term: string;
    term_type: string;
    risk_notes: string;
    translations: Record<string, { preferred: string; notes: string; alternatives: string[] }>;
  }[],
  cultural: {
    term: string;
    offset: number;
    length: number;
    culture_gap: "low" | "medium" | "high";
    suggested_rendering: string;
    reason: string;
    term_type: string;
  }[],
  activeLang: string,
): HighlightSpan[] {
  const glossarySpans: HighlightSpan[] = [];
  for (const t of glossary) {
    const label =
      SYSTEM_GLOSSARY_TERM_TYPE_LABELS[t.term_type] || DEFAULT_TERM_TYPE_LABEL;
    const preferred =
      t.translations[activeLang]?.preferred ??
      t.translations["en-GB"]?.preferred ??
      undefined;
    for (const offset of findAllOccurrences(text, t.source_term)) {
      glossarySpans.push({
        start: offset,
        end: offset + t.source_term.length,
        text: t.source_term,
        source: "glossary",
        term_type: t.term_type,
        label,
        risk_notes: t.risk_notes || undefined,
        suggestion: preferred,
      });
    }
  }

  // glossary 区间集合，用于吸收重叠的 cultural 区间（glossary 优先）
  const overlapsGlossary = (start: number, end: number) =>
    glossarySpans.some((g) => start < g.end && end > g.start);

  const culturalSpans: HighlightSpan[] = [];
  for (const c of cultural) {
    if (overlapsGlossary(c.offset, c.offset + c.length)) continue;
    culturalSpans.push({
      start: c.offset,
      end: c.offset + c.length,
      text: c.term,
      source: "cultural",
      term_type: c.term_type,
      label: CULTURAL_TERM_LABEL,
      suggestion: c.suggested_rendering || undefined,
      reason: c.reason || undefined,
      culture_gap: c.culture_gap,
    });
  }

  // 合并、按 start 升序、start 相同时 glossary 优先
  return [...glossarySpans, ...culturalSpans].sort((a, b) =>
    a.start !== b.start ? a.start - b.start : a.source === "glossary" ? -1 : 1,
  );
}

export function InlineHighlighter() {
  const text = useWorkspaceStore((s) => s.input.text);
  const setText = useWorkspaceStore((s) => s.setText);
  const activeLang = useWorkspaceStore((s) => s.activeLanguage);
  const detectedTerms = useGlossaryStore((s) => s.detectedTerms);
  const culturalTerms = useGlossaryStore((s) => s.culturalTerms);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mirrorRef = useRef<HTMLDivElement>(null);

  const spans = useMemo(
    () => buildSpans(text, detectedTerms, culturalTerms, activeLang),
    [text, detectedTerms, culturalTerms, activeLang],
  );

  // 滚动同步：textarea 滚动时镜像层跟随，保证高亮位置对齐
  const handleScroll = useCallback(() => {
    if (textareaRef.current && mirrorRef.current) {
      mirrorRef.current.scrollTop = textareaRef.current.scrollTop;
      mirrorRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, []);

  // 将原文按区间切片为段：非高亮段纯文本，高亮段 <mark>
  const segments = useMemo(() => {
    const segs: { text: string; span?: HighlightSpan }[] = [];
    let cursor = 0;
    for (const span of spans) {
      if (span.start > cursor) segs.push({ text: text.slice(cursor, span.start) });
      segs.push({ text: span.text, span });
      cursor = span.end;
    }
    if (cursor < text.length) segs.push({ text: text.slice(cursor) });
    return segs;
  }, [text, spans]);

  return (
    <div className="relative h-full w-full">
      {/*
        层叠设计（overlay 高亮器标准技巧）：
        - textarea（z-0，底层）：bg-white + 可见文字 + 可见光标，接收输入与非高亮区点击
        - 镜像 div（z-10，顶层）：pointer-events:none（容器）→ 非高亮区点击穿透到 textarea；
          <mark> 设 pointer-events:auto → 可 hover 弹出 Popover。
        - 镜像文字 text-transparent，避免与 textarea 文字重叠重影；
          <mark> 用半透明底色作为高亮带，textarea 文字透过带可见。
        - 已知取舍：直接点击高亮字符不会定位光标（mark 拦截），用户可点击邻位或用方向键。
        - overlay 架构不修改 textarea，故 IME 组合输入天然不受干扰。
      */}
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onScroll={handleScroll}
        placeholder={"将中文文本粘贴至此\n支持 .txt .docx .pdf（< 10MB）"}
        className={`absolute inset-0 z-0 resize-none rounded-md border border-border bg-white text-foreground caret-teal-600 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring ${MIRROR_TEXT_CLASS}`}
      />
      <div
        ref={mirrorRef}
        aria-hidden="true"
        className={`pointer-events-none absolute inset-0 z-10 overflow-auto rounded-md border border-transparent text-transparent ${MIRROR_TEXT_CLASS}`}
      >
        {segments.map((seg, i) =>
          seg.span ? (
            <Popover key={i}>
              <PopoverTrigger
                nativeButton={false}
                render={
                  <mark
                    data-span-key={`${seg.span.start}-${seg.span.end}`}
                    className={`pointer-events-auto relative cursor-help whitespace-pre-wrap rounded px-0.5 ${
                      seg.span.source === "cultural"
                        ? CULTURAL_HIGHLIGHT_CLASS
                        : TERM_TYPE_BADGE_CLASS[seg.span.term_type] ||
                          DEFAULT_TERM_TYPE_BADGE_CLASS
                    }`}
                  >
                    {seg.text}
                  </mark>
                }
                openOnHover
                delay={0}
                closeDelay={0}
              />
              <PopoverContent
                side="top"
                align="start"
                sideOffset={4}
                className="w-64 p-2"
              >
                <div className="text-xs font-semibold text-foreground">
                  {seg.span.text}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {seg.span.label}
                  {seg.span.culture_gap && ` · ${seg.span.culture_gap}`}
                </div>
                {seg.span.suggestion && (
                  <div className="mt-1 text-xs text-teal-700">
                    建议译法：{seg.span.suggestion}
                  </div>
                )}
                {seg.span.reason && (
                  <div className="mt-1 text-xs text-orange-700">
                    理由：{seg.span.reason}
                  </div>
                )}
                {seg.span.risk_notes && (
                  <div className="mt-1 text-xs text-orange-600">
                    ⚠ {seg.span.risk_notes}
                  </div>
                )}
              </PopoverContent>
            </Popover>
          ) : (
            <span key={i}>{seg.text}</span>
          ),
        )}
      </div>
    </div>
  );
}
