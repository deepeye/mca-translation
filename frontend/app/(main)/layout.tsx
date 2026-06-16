"use client";

import Link from "next/link";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center gap-6 bg-teal-dark px-6 text-sm text-teal-lightest">
        <Link href="/workspace" className="text-lg font-bold text-terracotta">
          CulturalBridge
        </Link>
        <nav className="flex gap-4">
          <Link href="/workspace" className="hover:text-white">工作台</Link>
        </nav>
        <div className="ml-auto">
          <button
            onClick={() => { localStorage.removeItem("token"); window.location.href = "/login"; }}
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
