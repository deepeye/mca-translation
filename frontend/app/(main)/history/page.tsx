"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useTranslationStore } from "@/stores/translation-store";
import { HistoryLayout } from "./components/history-layout";
import { FilterBar, type FilterValues } from "./components/filter-bar";
import { TaskList } from "./components/task-list";
import { DetailPanel, type JobDetailData } from "./components/detail-panel";
import { HistoryEmpty, HistorySkeleton } from "./components/history-empty";
import type { JobListItemData } from "./components/task-card";
import type { TranslationResultData } from "./components/translation-summary";

export default function HistoryPage() {
  const [jobs, setJobs] = useState<JobListItemData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterValues>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobDetailData | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const selectedJobRef = useRef<string | null>(null);

  const router = useRouter();
  const workspaceLoadFromHistory = useWorkspaceStore((s) => s.loadFromHistory);
  const translationLoadFromHistory = useTranslationStore((s) => s.loadFromHistory);

  // Fetch job list
  const fetchJobs = useCallback(async (currentFilters: FilterValues) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.listJobs({
        genre: currentFilters.genre,
        status: currentFilters.status,
      });
      setJobs(data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchJobs(filters);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle filter change
  const handleFilterChange = useCallback(
    (newFilters: FilterValues) => {
      setFilters(newFilters);
      setSelectedId(null);
      setSelectedJob(null);
      setDetailError(null);
      selectedJobRef.current = null;
      fetchJobs(newFilters);
    },
    [fetchJobs],
  );

  // Handle job selection — load full detail
  const handleSelectJob = useCallback(async (jobId: string) => {
    setSelectedId(jobId);
    selectedJobRef.current = jobId;
    setIsLoadingDetail(true);
    setSelectedJob(null);
    setDetailError(null);
    try {
      const data = await apiClient.get(`/api/jobs/${jobId}`);
      if (selectedJobRef.current === jobId) {
        setSelectedJob(data);
      }
    } catch (err) {
      if (selectedJobRef.current === jobId) {
        setDetailError(err instanceof Error ? err.message : "加载详情失败");
      }
    } finally {
      if (selectedJobRef.current === jobId) {
        setIsLoadingDetail(false);
      }
    }
  }, []);

  // Handle "加载到工作台"
  const handleLoadToWorkspace = useCallback(
    (job: JobDetailData) => {
      workspaceLoadFromHistory(job);
      translationLoadFromHistory(job.results);
      router.push("/workspace");
    },
    [workspaceLoadFromHistory, translationLoadFromHistory, router],
  );

  // Handle delete
  const handleDelete = useCallback(
    async (jobId: string) => {
      setIsDeleting(true);
      try {
        await apiClient.delete(`/api/jobs/${jobId}`);
        setJobs((prev) => prev.filter((j) => j.id !== jobId));
        if (selectedId === jobId) {
          setSelectedId(null);
          setSelectedJob(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "删除失败");
      } finally {
        setIsDeleting(false);
      }
    },
    [selectedId],
  );

  // Render left panel content
  const renderLeftContent = () => {
    if (error) {
      return (
        <div className="flex flex-col items-center gap-2 py-10">
          <p className="text-sm text-destructive">加载失败: {error}</p>
          <button
            onClick={() => fetchJobs(filters)}
            className="text-sm text-teal hover:text-teal-light cursor-pointer"
          >
            重试
          </button>
        </div>
      );
    }

    if (isLoading) {
      return <HistorySkeleton />;
    }

    if (jobs.length === 0) {
      return (
        <HistoryEmpty
          isAbsoluteEmpty={!filters.genre && !filters.status}
          onClearFilter={filters.genre || filters.status ? () => handleFilterChange({}) : undefined}
        />
      );
    }

    return <TaskList jobs={jobs} selectedId={selectedId} onSelect={handleSelectJob} />;
  };

  // Render right panel content
  const renderRightContent = () => {
    if (isLoadingDetail) {
      return <HistorySkeleton />;
    }
    if (detailError) {
      return (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-destructive">加载失败: {detailError}</p>
        </div>
      );
    }
    return (
      <DetailPanel
        job={selectedJob}
        onLoadToWorkspace={handleLoadToWorkspace}
        onDelete={handleDelete}
        isDeleting={isDeleting}
      />
    );
  };

  return (
    <HistoryLayout
      filterBar={
        <FilterBar values={filters} onChange={handleFilterChange} />
      }
      taskList={renderLeftContent()}
      detailPanel={renderRightContent()}
    />
  );
}
