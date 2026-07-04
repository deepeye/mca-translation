"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { UsersTable, AdminUser } from "@/components/admin/users-table";

export default function AdminUsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const data = await apiClient.get("/api/admin/users");
      setUsers(data);
    } catch {
      // 非管理员会被后端 403，前端也兜底跳走
      router.push("/workspace");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) return <div className="p-6 text-muted-foreground">加载中...</div>;

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="mb-6 text-2xl font-bold font-heading text-teal-dark">用户管理</h1>
      <div className="rounded-lg border border-border bg-white p-6">
        <UsersTable users={users} onChanged={load} />
      </div>
    </div>
  );
}
