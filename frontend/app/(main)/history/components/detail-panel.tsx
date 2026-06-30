"use client";

import { useState } from "react";
import { SourceTextView } from "./source-text-view";
import { TranslationSummary, type TranslationResultData } from "./translation-summary";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export interface JobDetailData {
  id: string;
  status: string;
  source_text: string;
  genre: string;
  strategy: string;
  target_languages: string[];
  cultural_sphere?: string | null;
  audience_type?: string | null;
  results: TranslationResultData[];
  created_at: string;
}

interface DetailPanelProps {
  job: JobDetailData | null;
  onLoadToWorkspace: (job: JobDetailData) => void;
  onDelete: (jobId: string) => void;
  isDeleting?: boolean;
}

const GENRE_LABELS: Record<string, string> = {
  political: "政治",
  news: "新闻",
  policy: "政策",
  brand: "品牌",
};

const STRATEGY_LABELS: Record<string, string> = {
  semantic_equivalence: "语义对等",
  audience_first: "受众优先",
  literal_reference: "字面引用",
};

export function DetailPanel({ job, onLoadToWorkspace, onDelete, isDeleting }: DetailPanelProps) {
  if (!job) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">请选择一条任务查看详情</p>
      </div>
    );
  }

  const strategyLabel = STRATEGY_LABELS[job.strategy] || job.strategy;
  const genreLabel = GENRE_LABELS[job.genre] || job.genre;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto">
      <h3 className="text-sm font-medium">翻译详情</h3>

      <SourceTextView text={job.source_text} />

      <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span>⚙️</span>
          <span>
            文体: {genreLabel} · 策略: {strategyLabel}
          </span>
        </div>
        {(job.cultural_sphere || job.audience_type) && (
          <div className="mt-1 ml-5">
            {job.cultural_sphere && <span>文化圈: {job.cultural_sphere} </span>}
            {job.audience_type && <span>· 受众: {job.audience_type}</span>}
          </div>
        )}
      </div>

      <TranslationSummary results={job.results} />

      <div className="mt-auto flex gap-2 border-t pt-3">
        <Button
          variant="default"
          size="sm"
          className="bg-teal hover:bg-teal-light text-white"
          onClick={() => onLoadToWorkspace(job)}
        >
          🔄 加载到工作台
        </Button>

        <AlertDialog>
          <AlertDialogTrigger className="inline-flex shrink-0 items-center justify-center rounded-lg border border-border bg-background bg-clip-padding px-2.5 text-xs font-medium whitespace-nowrap text-destructive hover:bg-muted hover:text-destructive transition-all duration-200 outline-none select-none h-7 gap-1 cursor-pointer">
            🗑️ 删除
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>确认删除</AlertDialogTitle>
              <AlertDialogDescription>
                确定要删除这条翻译记录吗？此操作不可撤销。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => onDelete(job.id)}
                disabled={isDeleting}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {isDeleting ? "删除中..." : "删除"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}
