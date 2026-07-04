import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import GlossaryPage from "../page";

const mockApiClient = vi.hoisted(() => ({
  listGlossaryEntries: vi.fn(),
  listUserGlossaryEntries: vi.fn(),
  createUserGlossaryEntry: vi.fn(),
  updateUserGlossaryEntry: vi.fn(),
  deleteUserGlossaryEntry: vi.fn(),
  autoFillUserGlossaryEntry: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: mockApiClient,
}));

describe("GlossaryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiClient.listGlossaryEntries.mockResolvedValue([]);
    mockApiClient.listUserGlossaryEntries.mockResolvedValue([]);
  });

  it('renders "+ 添加译法" button and opens language dropdown on click', async () => {
    render(<GlossaryPage />);

    expect(screen.getByText("+ 添加译法")).toBeInTheDocument();

    fireEvent.click(screen.getByText("+ 添加译法"));

    await waitFor(() => {
      expect(screen.getByText("添加")).toBeInTheDocument();
    });
  });

  it("calls createUserGlossaryEntry with correct translations shape on save", async () => {
    mockApiClient.createUserGlossaryEntry.mockResolvedValue({
      id: "new-1",
      source_term: "一带一路",
      term_type: "user_defined",
      translations: {
        "en-GB": { preferred: "BRI", alternatives: [], notes: "" },
      },
      risk_notes: "",
      applicable_genres: [],
    });

    render(<GlossaryPage />);

    const sourceInput = screen.getByPlaceholderText("中文术语");
    fireEvent.change(sourceInput, { target: { value: "一带一路" } });

    const preferredInput = screen.getByPlaceholderText("首选译法");
    fireEvent.change(preferredInput, { target: { value: "BRI" } });

    fireEvent.click(screen.getByText("保存术语"));

    await waitFor(() => {
      expect(mockApiClient.createUserGlossaryEntry).toHaveBeenCalledWith(
        expect.objectContaining({
          source_term: "一带一路",
          translations: {
            "en-GB": { preferred: "BRI", alternatives: [], notes: "" },
          },
        }),
      );
    });
  });

  it("shows +2 count badge for entry with en-GB, ar, de-DE translations", async () => {
    const entries = [
      {
        id: "1",
        source_term: "测试",
        term_type: "user_defined",
        translations: {
          "en-GB": { preferred: "test", alternatives: [], notes: "" },
          ar: { preferred: "اختبار", alternatives: [], notes: "" },
          "de-DE": { preferred: "Test", alternatives: [], notes: "" },
        },
        risk_notes: "",
        applicable_genres: [],
      },
    ];

    mockApiClient.listUserGlossaryEntries.mockResolvedValue(entries);

    render(<GlossaryPage />);

    await waitFor(() => {
      expect(screen.getByText("测试")).toBeInTheDocument();
    });

    expect(screen.getByText("+2")).toBeInTheDocument();
  });

  it("calls autoFillUserGlossaryEntry when auto-fill button is clicked in edit mode", async () => {
    const entry = {
      id: "entry-1",
      source_term: "autofill-test",
      term_type: "user_defined",
      translations: {
        "en-GB": { preferred: "test en", alternatives: [], notes: "" },
      },
      risk_notes: "",
      applicable_genres: [],
    };

    mockApiClient.listUserGlossaryEntries.mockResolvedValue([entry]);
    mockApiClient.autoFillUserGlossaryEntry.mockResolvedValue({
      entry,
      filled_languages: [],
      skipped: [],
    });

    render(<GlossaryPage />);

    await waitFor(() => {
      expect(screen.getByText("autofill-test")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("编辑"));

    const autoFillBtn = screen.getByText(/一键补齐/);
    expect(autoFillBtn).toBeInTheDocument();

    fireEvent.click(autoFillBtn);

    await waitFor(() => {
      expect(mockApiClient.autoFillUserGlossaryEntry).toHaveBeenCalledWith("entry-1");
    });
  });
});
