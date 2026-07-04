"use client";

import { CreditTransaction } from "@/lib/credits-api";

const TYPE_LABEL: Record<string, string> = {
  consume: "消费",
  refund: "退还",
  admin_topup: "管理员充值",
  admin_revoke: "管理员扣减",
  signup_bonus: "注册赠送",
};

export function TransactionsTable({ items }: { items: CreditTransaction[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">暂无交易记录</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left text-muted-foreground">
          <th className="py-2">时间</th>
          <th>类型</th>
          <th>变动</th>
          <th>原因</th>
        </tr>
      </thead>
      <tbody>
        {items.map((t) => (
          <tr key={t.id} className="border-b">
            <td className="py-2">{new Date(t.created_at).toLocaleString("zh-CN")}</td>
            <td>{TYPE_LABEL[t.tx_type] || t.tx_type}</td>
            <td className={t.delta >= 0 ? "text-teal-dark" : "text-danger"}>
              {t.delta >= 0 ? "+" : ""}{t.delta}
            </td>
            <td className="text-muted-foreground">{t.reason || "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
