import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UserFormModal } from "../user-form-modal";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: vi.fn().mockResolvedValue({ id: "new-id" }),
    put: vi.fn().mockResolvedValue({ id: "edit-id" }),
  },
}));

describe("UserFormModal", () => {
  const onClose = vi.fn();
  const onSubmitted = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a user successfully", async () => {
    const { apiClient } = await import("@/lib/api-client");
    render(
      <UserFormModal open={true} onClose={onClose} onSubmitted={onSubmitted} />
    );

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "newuser" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "pass123" } });
    fireEvent.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/api/admin/users", {
        username: "newuser",
        password: "pass123",
        is_admin: false,
      });
      expect(onSubmitted).toHaveBeenCalled();
    });
  });

  it("edits a user successfully", async () => {
    const { apiClient } = await import("@/lib/api-client");
    render(
      <UserFormModal
        userId="user-1"
        username="alice"
        currentIsAdmin={false}
        open={true}
        onClose={onClose}
        onSubmitted={onSubmitted}
      />
    );

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "alice_updated" } });
    fireEvent.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith("/api/admin/users/user-1", {
        username: "alice_updated",
      });
      expect(onSubmitted).toHaveBeenCalled();
    });
  });

  it("rejects empty username on create", async () => {
    render(
      <UserFormModal open={true} onClose={onClose} onSubmitted={onSubmitted} />
    );

    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "pass123" } });
    fireEvent.click(screen.getByText("创建"));

    expect(onSubmitted).not.toHaveBeenCalled();
    expect(screen.getByText("请输入用户名")).toBeInTheDocument();
  });

  it("rejects empty password on create", async () => {
    render(
      <UserFormModal open={true} onClose={onClose} onSubmitted={onSubmitted} />
    );

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "newuser" } });
    fireEvent.click(screen.getByText("创建"));

    expect(onSubmitted).not.toHaveBeenCalled();
    expect(screen.getByText("请输入密码")).toBeInTheDocument();
  });
});
