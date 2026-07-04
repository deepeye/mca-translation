"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";
import { AdjustModal } from "./adjust-modal";
import { UserFormModal } from "./user-form-modal";
import { DeleteConfirmDialog } from "./delete-confirm-dialog";

export interface AdminUser {
  id: string;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  credit_balance: number;
  last_active: string | null;
  created_at: string;
}

export function UsersTable({
  users,
  onChanged,
}: {
  users: AdminUser[];
  onChanged: () => void;
}) {
  const [actionUser, setActionUser] = useState<AdminUser | null>(null);
  const [showAdjust, setShowAdjust] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  function closeAll() {
    setShowAdjust(false);
    setShowEdit(false);
    setShowDelete(false);
    setOpenMenuId(null);
  }

  function handleAction(u: AdminUser) {
    setActionUser(u);
    setOpenMenuId(u.id);
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          共 {users.length} 个用户
        </span>
        <button
          onClick={() => { setShowCreate(true); setActionUser(null); }}
          className="rounded bg-teal px-4 py-1.5 text-sm text-white cursor-pointer"
        >
          ＋创建用户
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2">用户名</th>
            <th>角色</th>
            <th>余额</th>
            <th>状态</th>
            <th>最近活跃</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b">
              <td className="py-2">{u.username}</td>
              <td>{u.is_admin ? "管理员" : "普通用户"}</td>
              <td className={u.credit_balance <= 0 ? "text-danger" : ""}>{u.credit_balance}</td>
              <td>
                <span className={u.is_active ? "text-green-600" : "text-muted-foreground"}>
                  {u.is_active ? "正常" : "已禁用"}
                </span>
              </td>
              <td className="text-muted-foreground">
                {u.last_active ? new Date(u.last_active).toLocaleString("zh-CN") : "-"}
              </td>
              <td className="relative">
                <button
                  onClick={() => handleAction(u)}
                  className="rounded px-2 py-1 text-sm text-muted-foreground hover:bg-muted cursor-pointer"
                >
                  ⋮
                </button>
                {openMenuId === u.id && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setOpenMenuId(null)} />
                    <div className="absolute right-0 z-50 mt-1 w-40 rounded-lg border border-border bg-white py-1 shadow-lg">
                      <button
                        onClick={() => { setShowAdjust(true); setOpenMenuId(null); }}
                        className="block w-full px-4 py-2 text-left text-sm hover:bg-muted cursor-pointer"
                      >
                        调整余额
                      </button>
                      <button
                        onClick={() => { setShowEdit(true); setOpenMenuId(null); }}
                        className="block w-full px-4 py-2 text-left text-sm hover:bg-muted cursor-pointer"
                      >
                        编辑
                      </button>
                      <div className="border-t border-border my-1" />
                      <button
                        onClick={async () => {
                          setOpenMenuId(null);
                          try {
                            await apiClient.patch(`/api/admin/users/${u.id}/status`, {
                              is_active: !u.is_active,
                            });
                            onChanged();
                          } catch (e) {
                            alert(e instanceof Error ? e.message : "操作失败");
                          }
                        }}
                        className="block w-full px-4 py-2 text-left text-sm hover:bg-muted cursor-pointer"
                      >
                        {u.is_active ? "禁用" : "启用"}
                      </button>
                      <button
                        onClick={() => { setShowDelete(true); setOpenMenuId(null); }}
                        className="block w-full px-4 py-2 text-left text-sm text-danger hover:bg-red-50 cursor-pointer"
                      >
                        删除
                      </button>
                    </div>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Modals */}
      {actionUser && showAdjust && (
        <AdjustModal
          userId={actionUser.id}
          username={actionUser.username}
          open={true}
          onClose={() => { setShowAdjust(false); setActionUser(null); }}
          onSubmitted={() => { closeAll(); onChanged(); }}
        />
      )}
      {actionUser && showEdit && (
        <UserFormModal
          userId={actionUser.id}
          username={actionUser.username}
          currentIsAdmin={actionUser.is_admin}
          open={true}
          onClose={() => { closeAll(); setActionUser(null); }}
          onSubmitted={() => { closeAll(); onChanged(); }}
        />
      )}
      {showCreate && (
        <UserFormModal
          open={true}
          onClose={() => { setShowCreate(false); }}
          onSubmitted={() => { setShowCreate(false); onChanged(); }}
        />
      )}
      {actionUser && showDelete && (
        <DeleteConfirmDialog
          userId={actionUser.id}
          username={actionUser.username}
          open={true}
          onClose={() => { closeAll(); setActionUser(null); }}
          onDeleted={() => { closeAll(); onChanged(); }}
        />
      )}
    </>
  );
}
