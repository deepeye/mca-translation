import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock app router before component render
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

// Mock state 可在不同 describe 间覆盖
const mockState = {
  balance: 42,
  isInsufficient: false,
  fetchBalance: vi.fn(),
};

// Mock store before importing component
// 组件使用 zustand 选择器写法 useCreditsStore((s) => s.x)，
// 因此 mock 需以 state 对象调用选择器。
vi.mock("@/stores/credits-store", () => ({
  useCreditsStore: vi.fn((selector: (s: unknown) => unknown) =>
    selector(mockState),
  ),
}));

import { BalanceBadge } from "@/components/balance-badge";

describe("BalanceBadge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockState.balance = 42;
    mockState.isInsufficient = false;
  });

  it("renders the balance number", () => {
    render(<BalanceBadge />);
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });

  it("does not show warning style when balance > 0", () => {
    const { container } = render(<BalanceBadge />);
    expect(container.querySelector(".text-danger")).toBeNull();
  });
});

describe("BalanceBadge insufficient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockState.balance = 0;
    mockState.isInsufficient = true;
  });

  it("shows warning styling when balance is 0", () => {
    const { container } = render(<BalanceBadge />);
    expect(container.querySelector(".text-danger")).not.toBeNull();
  });
});
