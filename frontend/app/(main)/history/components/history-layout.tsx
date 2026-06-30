"use client";

import type { ReactNode } from "react";

interface HistoryLayoutProps {
  filterBar: ReactNode;
  taskList: ReactNode;
  detailPanel: ReactNode;
}

export function HistoryLayout({ filterBar, taskList, detailPanel }: HistoryLayoutProps) {
  return (
    <div className="flex h-[calc(100dvh-3.5rem)] gap-0">
      {/* Left panel */}
      <div className="flex w-[40%] flex-col border-r border-border p-3 gap-3">
        {filterBar}
        <div className="flex-1 overflow-y-auto">
          {taskList}
        </div>
      </div>
      {/* Right panel */}
      <div className="w-[60%] p-4 overflow-y-auto">
        {detailPanel}
      </div>
    </div>
  );
}
