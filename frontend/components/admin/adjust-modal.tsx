"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";

interface Props {
  userId: string;
  username: string;
  open: boolean;
  onClose: () => void;
  onSubmitted: (delta: number, reason: string) => void;
}

export function AdjustModal({ userId, username, open, onClose, onSubmitted }: Props) {
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  async function handleSubmit() {
    if (!reason.trim()) {
      setError("请填写原因");
      return;
    }
    const n = parseInt(delta, 10);
    if (Number.isNaN(n)) {
      setError("请输入有效整数");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.post(`/api/admin/users/${userId}/credits`, {
        delta: n,
        reason: reason.trim(),
      });
      onSubmitted(n, reason.trim());
      setDelta("");
      setReason("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h3 className="mb-4 text-lg font-semibold">调整信用分 — {username}</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-muted-foreground mb-1" htmlFor="delta">
              变动额度（正数充值，负数扣减）
            </label>
            <input
              id="delta"
              aria-label="变动额度"
              type="number"
              value={delta}
              onChange={(e) => setDelta(e.target.value)}
              className="w-full rounded border border-border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-muted-foreground mb-1" htmlFor="reason">
              原因
            </label>
            <textarea
              id="reason"
              aria-label="原因"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full rounded border border-border px-3 py-2"
              rows={2}
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm bg-muted text-muted-foreground cursor-pointer"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="rounded px-4 py-2 text-sm bg-teal text-white cursor-pointer disabled:opacity-50"
          >
            {submitting ? "提交中..." : "确认"}
          </button>
        </div>
      </div>
    </div>
  );
}
