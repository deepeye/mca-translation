"use client";

import { ReviewInputPanel } from "@/components/review/review-input-panel";
import { ReviewResultPanel } from "@/components/review/review-result-panel";
import { ReviewReportPanel } from "@/components/review/review-report-panel";
import { useReviewStore } from "@/stores/review-store";

export default function ReviewPage() {
  const result = useReviewStore((s) => s.result);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col gap-3 p-4">
      <div className="flex flex-1 gap-3 overflow-hidden">
        <div className="w-[42%] min-w-[320px] overflow-hidden">
          <ReviewInputPanel />
        </div>
        <div className="flex flex-1 flex-col gap-3 overflow-hidden">
          <ReviewResultPanel />
        </div>
      </div>
      {result && (
        <div className="shrink-0">
          <ReviewReportPanel />
        </div>
      )}
    </div>
  );
}
