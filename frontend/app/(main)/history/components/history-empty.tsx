"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

interface HistoryEmptyProps {
  /** true = no records at all, false = filter returned no results */
  isAbsoluteEmpty?: boolean;
  onClearFilter?: () => void;
}

export function HistoryEmpty({ isAbsoluteEmpty, onClearFilter }: HistoryEmptyProps) {
  if (isAbsoluteEmpty) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
        <div className="text-6xl">📋</div>
        <h3 className="text-lg font-medium text-muted-foreground">
          还没有翻译记录
        </h3>
        <p className="text-sm text-muted-foreground">
          开始你的第一次翻译吧
        </p>
        <Link href="/workspace">
          <Button variant="default" className="bg-teal hover:bg-teal-light text-white">
            去翻译
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
      <div className="text-6xl">🔍</div>
      <h3 className="text-lg font-medium text-muted-foreground">
        没有符合条件的记录
      </h3>
      <p className="text-sm text-muted-foreground">
        尝试调整筛选条件
      </p>
      {onClearFilter && (
        <Button variant="outline" size="sm" onClick={onClearFilter}>
          清除筛选
        </Button>
      )}
    </div>
  );
}

export function HistorySkeleton() {
  return (
    <div className="flex flex-col gap-2 p-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />
      ))}
    </div>
  );
}
