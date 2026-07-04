import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DeleteConfirmDialog } from "../delete-confirm-dialog";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    delete: vi.fn().mockResolvedValue(undefined),
  },
}));

describe("DeleteConfirmDialog", () => {
  const onClose = vi.fn();
  const onDeleted = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("confirms deletion", async () => {
    const { apiClient } = await import("@/lib/api-client");
    render(
      <DeleteConfirmDialog
        userId="user-1"
        username="alice"
        open={true}
        onClose={onClose}
        onDeleted={onDeleted}
      />
    );

    expect(screen.getByText(/alice/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith("/api/admin/users/user-1");
      expect(onDeleted).toHaveBeenCalled();
    });
  });

  it("cancels deletion", async () => {
    render(
      <DeleteConfirmDialog
        userId="user-1"
        username="alice"
        open={true}
        onClose={onClose}
        onDeleted={onDeleted}
      />
    );

    fireEvent.click(screen.getByText("取消"));
    expect(onClose).toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
  });
});
