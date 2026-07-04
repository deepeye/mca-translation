import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AdjustModal } from "../adjust-modal";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: vi.fn().mockResolvedValue({ balance: 500 }),
  },
}));

describe("AdjustModal", () => {
  const onClose = vi.fn();
  const onSubmitted = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls onSubmitted with delta and reason", async () => {
    render(
      <AdjustModal
        userId="user-1"
        username="alice"
        open={true}
        onClose={onClose}
        onSubmitted={onSubmitted}
      />
    );

    fireEvent.change(screen.getByLabelText("变动额度"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("原因"), { target: { value: "月度充值" } });
    fireEvent.click(screen.getByText("确认"));

    await waitFor(() => {
      expect(onSubmitted).toHaveBeenCalledWith(500, "月度充值");
    });
  });

  it("rejects empty reason", async () => {
    render(
      <AdjustModal
        userId="user-1"
        username="alice"
        open={true}
        onClose={onClose}
        onSubmitted={onSubmitted}
      />
    );
    fireEvent.change(screen.getByLabelText("变动额度"), { target: { value: "100" } });
    fireEvent.click(screen.getByText("确认"));
    // 未填原因时不提交
    expect(onSubmitted).not.toHaveBeenCalled();
    expect(screen.getByText(/请填写原因/)).toBeInTheDocument();
  });
});
