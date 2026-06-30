"use client";

interface SourceTextViewProps {
  text: string;
}

export function SourceTextView({ text }: SourceTextViewProps) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-sm">📝</span>
        <span className="text-xs font-medium text-muted-foreground">原文</span>
      </div>
      <div className="max-h-40 overflow-y-auto text-sm leading-relaxed">
        {text}
      </div>
    </div>
  );
}
