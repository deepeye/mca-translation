"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";

interface Props {
  userId?: string;        // undefined = create mode, defined = edit mode
  username?: string;      // for display in title
  currentIsAdmin?: boolean; // current admin status (edit mode only)
  open: boolean;
  onClose: () => void;
  onSubmitted: () => void;
}

export function UserFormModal({ userId, username, currentIsAdmin, open, onClose, onSubmitted }: Props) {
  const isEdit = !!userId;
  const [formUsername, setFormUsername] = useState("");
  const [formPassword, setFormPassword] = useState("");
  const [formIsAdmin, setFormIsAdmin] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setFormUsername(username ?? "");
      setFormPassword("");
      setFormIsAdmin(currentIsAdmin ?? false);
      setError(null);
    }
  }, [open, isEdit, username, currentIsAdmin]);

  if (!open) return null;

  async function handleSubmit() {
    if (!formUsername.trim()) {
      setError("请输入用户名");
      return;
    }
    if (!isEdit && !formPassword.trim()) {
      setError("请输入密码");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      if (isEdit) {
        const body: Record<string, unknown> = {};
        if (formUsername.trim() && formUsername.trim() !== username) body.username = formUsername.trim();
        if (formPassword) body.password = formPassword;
        if (currentIsAdmin !== undefined && formIsAdmin !== currentIsAdmin) body.is_admin = formIsAdmin;
        await apiClient.put(`/api/admin/users/${userId}`, body);
      } else {
        await apiClient.post("/api/admin/users", {
          username: formUsername.trim(),
          password: formPassword,
          is_admin: formIsAdmin,
        });
      }
      onSubmitted();
      setFormUsername("");
      setFormPassword("");
      setFormIsAdmin(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h3 className="mb-4 text-lg font-semibold">
          {isEdit ? `编辑用户 — ${username}` : "创建用户"}
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-muted-foreground mb-1" htmlFor="uf-username">
              用户名
            </label>
            <input
              id="uf-username"
              aria-label="用户名"
              type="text"
              value={formUsername}
              onChange={(e) => setFormUsername(e.target.value)}
              className="w-full rounded border border-border px-3 py-2"
              maxLength={64}
            />
          </div>
          <div>
            <label className="block text-sm text-muted-foreground mb-1" htmlFor="uf-password">
              密码{isEdit ? "（留空不修改）" : ""}
            </label>
            <input
              id="uf-password"
              aria-label="密码"
              type="password"
              value={formPassword}
              onChange={(e) => setFormPassword(e.target.value)}
              className="w-full rounded border border-border px-3 py-2"
              minLength={isEdit ? 0 : 6}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              id="uf-is_admin"
              aria-label="管理员权限"
              type="checkbox"
              checked={formIsAdmin}
              onChange={(e) => setFormIsAdmin(e.target.checked)}
              className="h-4 w-4"
            />
            <label htmlFor="uf-is_admin" className="text-sm text-muted-foreground">
              管理员权限
            </label>
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
            {submitting ? "提交中..." : (isEdit ? "保存" : "创建")}
          </button>
        </div>
      </div>
    </div>
  );
}
