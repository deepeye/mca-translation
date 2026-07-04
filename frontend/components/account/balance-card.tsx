"use client";

export function BalanceCard({ balance }: { balance: number | null }) {
  const insufficient = balance !== null && balance <= 0;
  return (
    <div className={`rounded-lg border p-6 ${insufficient ? "border-danger bg-danger/5" : "border-border bg-white"}`}>
      <p className="text-sm text-muted-foreground">当前余额</p>
      <p className={`mt-2 text-4xl font-bold ${insufficient ? "text-danger" : "text-teal-dark"}`}>
        {balance === null ? "..." : balance.toLocaleString()}
      </p>
      {insufficient && (
        <p className="mt-3 text-sm text-danger">信用分已用完，请联系管理员充值</p>
      )}
    </div>
  );
}
