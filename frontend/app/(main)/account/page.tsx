"use client";

import { useEffect, useState } from "react";
import { useCreditsStore } from "@/stores/credits-store";
import { fetchTransactions, fetchTrend, CreditTransaction, DailyConsumption } from "@/lib/credits-api";
import { BalanceCard } from "@/components/account/balance-card";
import { ConsumptionChart } from "@/components/account/consumption-chart";
import { TransactionsTable } from "@/components/account/transactions-table";

export default function AccountPage() {
  const balance = useCreditsStore((s) => s.balance);
  const fetchBalance = useCreditsStore((s) => s.fetchBalance);
  const [days, setDays] = useState<7 | 30>(7);
  const [trend, setTrend] = useState<DailyConsumption[]>([]);
  const [txs, setTxs] = useState<CreditTransaction[]>([]);

  useEffect(() => {
    fetchBalance();
  }, [fetchBalance]);

  useEffect(() => {
    fetchTrend(days).then(setTrend).catch(() => setTrend([]));
  }, [days]);

  useEffect(() => {
    fetchTransactions(50).then(setTxs).catch(() => setTxs([]));
  }, [balance]);

  return (
    <div className="mx-auto max-w-4xl p-6 space-y-6">
      <h1 className="text-2xl font-bold font-heading text-teal-dark">用户中心</h1>
      <BalanceCard balance={balance} />
      <div className="rounded-lg border border-border bg-white p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">消费趋势</h2>
          <div className="flex gap-2">
            {([7, 30] as const).map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`rounded px-3 py-1 text-xs cursor-pointer ${
                  days === d ? "bg-teal text-white" : "bg-muted text-muted-foreground"
                }`}
              >
                {d} 天
              </button>
            ))}
          </div>
        </div>
        <ConsumptionChart data={trend} />
      </div>
      <div className="rounded-lg border border-border bg-white p-6">
        <h2 className="text-lg font-semibold mb-4">交易历史</h2>
        <TransactionsTable items={txs} />
      </div>
    </div>
  );
}
