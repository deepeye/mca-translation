"use client";

import { useWorkspaceStore } from "@/stores/workspace-store";

export function TextEditor() {
  const text = useWorkspaceStore((s) => s.input.text);
  const setText = useWorkspaceStore((s) => s.setText);

  return (
    <div className="relative flex-1">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={"将中文文本粘贴至此，或上传文件\n支持 .txt .docx .pdf（< 10MB）"}
        className="h-full w-full resize-none rounded-md border border-border bg-white p-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <div className="absolute bottom-2 right-3 text-xs text-muted-foreground">
        {text.length} / 10000
      </div>
    </div>
  );
}
