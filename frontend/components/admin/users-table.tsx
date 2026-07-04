"use client";

import { useState } from "react";
import { AdjustModal } from "./adjust-modal";

export interface AdminUser {
  id: string;
  username: string;
  is_admin: boolean;
  credit_balance: number;
  last_active: string | null;
}

export function UsersTable({
  users,
  onChanged,
}: {
  users: AdminUser[];
  onChanged: () => void;
}) {
  const [adjusting, setAdjusting] = useState<AdminUser | null>(null);

  return (
    <>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2">用户名</th>
            <th>角色</th>
            <th>余额</th>
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
              <td className="text-muted-foreground">
                {u.last_active ? new Date(u.last_active).toLocaleString("zh-CN") : "-"}
              </td>
              <td>
                <button
                  onClick={() => setAdjusting(u)}
                  className="rounded bg-teal px-3 py-1 text-xs text-white cursor-pointer"
                >
                  调整
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {adjusting && (
        <AdjustModal
          userId={adjusting.id}
          username={adjusting.username}
          open={true}
          onClose={() => setAdjusting(null)}
          onSubmitted={() => {
            setAdjusting(null);
            onChanged();
          }}
        />
      )}
    </>
  );
}
