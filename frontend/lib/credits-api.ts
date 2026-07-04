import { apiClient } from "@/lib/api-client";

export interface CreditTransaction {
  id: string;
  delta: number;
  tx_type: string;
  reason: string | null;
  job_id: string | null;
  review_id: string | null;
  created_at: string;
}

export interface DailyConsumption {
  date: string;
  consumed: number;
}

export async function fetchTransactions(limit = 50): Promise<CreditTransaction[]> {
  return apiClient.get(`/api/credits/transactions?limit=${limit}`);
}

export async function fetchTrend(days: 7 | 30): Promise<DailyConsumption[]> {
  return apiClient.get(`/api/credits/trend?days=${days}`);
}
