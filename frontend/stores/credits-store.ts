import { create } from "zustand";
import { apiClient } from "@/lib/api-client";

interface CreditsState {
  balance: number | null;
  isInsufficient: boolean;
  isAdmin: boolean;
  fetchBalance: () => Promise<void>;
  setBalance: (n: number) => void;
}

export const useCreditsStore = create<CreditsState>((set) => ({
  balance: null,
  isInsufficient: false,
  isAdmin: false,
  setBalance: (n) => set({ balance: n, isInsufficient: n <= 0 }),
  fetchBalance: async () => {
    try {
      const data = await apiClient.get("/api/credits/balance");
      set({
        balance: data.balance,
        isInsufficient: data.balance <= 0,
        isAdmin: data.is_admin,
      });
    } catch {
      // 静默失败：余额徽章不应阻塞主界面
    }
  },
}));
