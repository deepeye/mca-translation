"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useCreditsStore } from "@/stores/credits-store";

export function BalanceBadge() {
  const router = useRouter();
  const balance = useCreditsStore((s) => s.balance);
  const isInsufficient = useCreditsStore((s) => s.isInsufficient);
  const fetchBalance = useCreditsStore((s) => s.fetchBalance);

  useEffect(() => {
    fetchBalance();
  }, [fetchBalance]);

  const insufficient = balance !== null && balance <= 0;

  return (
    <button
      onClick={() => router.push("/account")}
      title={insufficient ? "信用分已用完，请联系管理员充值" : "查看信用分详情"}
      className={`cursor-pointer text-sm ${
        insufficient ? "text-danger font-bold" : "text-teal-lightest hover:text-white"
      }`}
    >
      {balance === null ? "..." : `🪙 ${balance.toLocaleString()}`}
    </button>
  );
}
