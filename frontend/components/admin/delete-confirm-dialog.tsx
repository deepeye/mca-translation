"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";

interface Props {
  userId: string;
  username: string;
  open: boolean;
  onClose: () => void;
  onDeleted: () => void;
}

export function DeleteConfirmDialog({ userId, username, open, onClose, onDeleted }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  async function handleDelete() {
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.delete(`/api/admin/users/${userId}`);
      onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-lg">
        <h3 className="mb-2 text-lg font-semibold">确认删除</h3>
        <p className="text-sm text-muted-foreground mb-4">
          确定要删除用户 <strong>{username}</strong> 吗？此操作不可恢复。
        </p>
        {error && <p className="text-sm text-danger mb-2">{error}</p>}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm bg-muted text-muted-foreground cursor-pointer"
          >
            取消
          </button>
          <button
            onClick={handleDelete}
            disabled={submitting}
            className="rounded px-4 py-2 text-sm bg-danger text-white cursor-pointer disabled:opacity-50"
          >
            {submitting ? "删除中..." : "确认删除"}
          </button>
        </div>
      </div>
    </div>
  );
}
