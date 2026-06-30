"use client";

import { TaskCard, type JobListItemData } from "./task-card";

interface TaskListProps {
  jobs: JobListItemData[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function TaskList({ jobs, selectedId, onSelect }: TaskListProps) {
  if (jobs.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 overflow-y-auto">
      {jobs.map((job) => (
        <TaskCard
          key={job.id}
          job={job}
          isSelected={job.id === selectedId}
          onClick={() => onSelect(job.id)}
        />
      ))}
    </div>
  );
}
