"use client";

import { useEffect } from "react";
import Link from "next/link";
import { BalanceBadge } from "@/components/balance-badge";
import { useCreditsStore } from "@/stores/credits-store";
import { loginPath } from "@/lib/base-path";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  const isAdmin = useCreditsStore((s) => s.isAdmin);
  const fetchBalance = useCreditsStore((s) => s.fetchBalance);
  useEffect(() => {
    fetchBalance();
  }, [fetchBalance]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center gap-6 bg-teal-dark px-6 text-sm text-teal-lightest shadow-sm shadow-teal-dark/20">
        <Link href="/workspace" className="text-lg font-bold font-heading tracking-tight text-terracotta">
          CulturalBridge
        </Link>
        <nav className="flex gap-4">
          <Link href="/workspace" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">工作台</Link>
          <Link href="/review" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">审校</Link>
          <Link href="/glossary" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">术语库</Link>
          <Link href="/history" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">历史</Link>
          <Link href="/help" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">使用手册</Link>
          {isAdmin && (
            <Link href="/admin/users" className="hover:text-white border-b-2 border-transparent hover:border-teal-light pb-0.5 transition-all duration-200">管理</Link>
          )}
        </nav>
        <div className="ml-auto flex items-center gap-4">
          <BalanceBadge />
          <button
            onClick={() => { localStorage.removeItem("token"); window.location.href = loginPath(); }}
            className="text-teal-light hover:text-white cursor-pointer"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
