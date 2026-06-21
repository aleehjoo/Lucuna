import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useCancelJob, useJob, useStartSearch } from "@/lib/hooks";
import { ApiError } from "@/lib/api";
import type { JobOut, LiveSearchCounts } from "@/lib/types";
import SearchPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useStartSearch: vi.fn(),
  useJob: vi.fn(),
  useCancelJob: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "proj-1" }),
}));

const mockUseStartSearch = useStartSearch as unknown as ReturnType<typeof vi.fn>;
const mockUseJob = useJob as unknown as ReturnType<typeof vi.fn>;
const mockUseCancelJob = useCancelJob as unknown as ReturnType<typeof vi.fn>;

function job(overrides: Partial<JobOut> = {}): JobOut {
  return {
    id: "job-1",
    project_id: "proj-1",
    kind: "live_search",
    status: "done",
    progress_pct: 100,
    step: null,
    counts: null,
    result_ref: null,
    error_detail: null,
    ...overrides,
  };
}

function freshOnlyCounts(): LiveSearchCounts {
  return {
    title: "Atomic Habits",
    review_count: 50,
    fresh_only: true,
    agreement_pct: 0,
    clusters: [],
    rating_avg: 4.2,
    rating_count: 13,
    rating_distribution: { "1": 1, "2": 1, "3": 2, "4": 4, "5": 5 },
    pack: {
      legend: {},
      instructions_to_model: {},
      known_limitations: {},
      target: { project: "Atomic Habits", bisac: [], mode: "single_title" },
      generated_at: "2026-06-20T00:00:00Z",
      provenance: { platforms_used: ["hardcover"], total_reviews: 13, cross_platform_agreement_pct: 0 },
      candidates: [
        {
          ref: "work",
          title_or_subject: "Atomic Habits",
          gap_score: 0,
          components: { demand: 0, supply_scarcity: 0, unmet_need: 0 },
          validity: {
            confidence: 0.2,
            sample_size: 13,
            platforms: ["hardcover"],
            oldest_signal: null,
            newest_signal: null,
            incomplete: true,
            blind_spot: false,
            recent_supply_surge: false,
          },
          top_complaints: [],
          demand_evidence: {},
        },
      ],
    },
  };
}

beforeEach(() => {
  mockUseStartSearch.mockReset();
  mockUseJob.mockReset();
  mockUseCancelJob.mockReset();
  mockUseCancelJob.mockReturnValue({ mutate: vi.fn(), isPending: false });
});

describe("SearchPage", () => {
  it("submits a title query and starts the search job", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ job_id: "job-1" });
    mockUseStartSearch.mockReturnValue({ mutateAsync, isPending: false });
    mockUseJob.mockReturnValue({ data: undefined, isLoading: false });

    render(<SearchPage />);

    fireEvent.change(screen.getByPlaceholderText("Search a book title or ISBN"), {
      target: { value: "Atomic Habits" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await vi.waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({ title: "Atomic Habits" });
    });
  });

  it("sends an isbn payload when the query looks like an ISBN", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ job_id: "job-1" });
    mockUseStartSearch.mockReturnValue({ mutateAsync, isPending: false });
    mockUseJob.mockReturnValue({ data: undefined, isLoading: false });

    render(<SearchPage />);

    fireEvent.change(screen.getByPlaceholderText("Search a book title or ISBN"), {
      target: { value: "978-0735211292" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await vi.waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({ isbn: "978-0735211292" });
    });
  });

  it("blocks submit with an inline message on an empty query", () => {
    const mutateAsync = vi.fn();
    mockUseStartSearch.mockReturnValue({ mutateAsync, isPending: false });
    mockUseJob.mockReturnValue({ data: undefined, isLoading: false });

    render(<SearchPage />);

    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(screen.getByText("Enter a book title or ISBN to search.")).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("renders the fresh-only SearchResult once the job is done, with no dead end on empty clusters", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ job_id: "job-1" });
    mockUseStartSearch.mockReturnValue({ mutateAsync, isPending: false });
    mockUseJob.mockReturnValue({
      data: job({ counts: freshOnlyCounts() as unknown as Record<string, unknown> }),
      isLoading: false,
    });

    render(<SearchPage />);

    fireEvent.change(screen.getByPlaceholderText("Search a book title or ISBN"), {
      target: { value: "Atomic Habits" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await vi.waitFor(() => {
      expect(screen.getByText("Atomic Habits")).toBeInTheDocument();
    });
    expect(screen.getByText("Fresh only")).toBeInTheDocument();
    expect(screen.getByText(/low signal: 50 reviews/)).toBeInTheDocument();
  });

  it("carries the hypothesis-not-a-finding posture on a rendered result", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ job_id: "job-1" });
    mockUseStartSearch.mockReturnValue({ mutateAsync, isPending: false });
    mockUseJob.mockReturnValue({
      data: job({ counts: freshOnlyCounts() as unknown as Record<string, unknown> }),
      isLoading: false,
    });

    render(<SearchPage />);

    fireEvent.change(screen.getByPlaceholderText("Search a book title or ISBN"), {
      target: { value: "Atomic Habits" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await vi.waitFor(() => {
      expect(
        screen.getByText(/treat each candidate as a hypothesis, not a finding/i),
      ).toBeInTheDocument();
    });
  });

  it("maps a 503 (Hardcover not configured) to a quiet, non-alarming notice, not a raw error", async () => {
    const mutateAsync = vi
      .fn()
      .mockRejectedValue(new ApiError("HARDCOVER_API_TOKEN not configured on the backend", 503));
    mockUseStartSearch.mockReturnValue({ mutateAsync, isPending: false });
    mockUseJob.mockReturnValue({ data: undefined, isLoading: false });

    render(<SearchPage />);

    fireEvent.change(screen.getByPlaceholderText("Search a book title or ISBN"), {
      target: { value: "Atomic Habits" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await vi.waitFor(() => {
      expect(
        screen.getByText(
          "Live search isn't available — the Hardcover key isn't configured on this instance.",
        ),
      ).toBeInTheDocument();
    });
    // Not rendered via the oxblood "something broke" path — the raw backend
    // detail string never reaches the screen.
    expect(
      screen.queryByText("HARDCOVER_API_TOKEN not configured on the backend"),
    ).not.toBeInTheDocument();
  });

  it("allows cancelling a running live-search job, which moves to the Cancelled state with no dead end", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ job_id: "job-1" });
    const cancelMutate = vi.fn();
    mockUseStartSearch.mockReturnValue({ mutateAsync, isPending: false });
    mockUseCancelJob.mockReturnValue({ mutate: cancelMutate, isPending: false });
    mockUseJob.mockReturnValue({
      data: job({ status: "running", progress_pct: 30, step: "clustering", counts: null }),
      isLoading: false,
    });

    const { rerender } = render(<SearchPage />);

    fireEvent.change(screen.getByPlaceholderText("Search a book title or ISBN"), {
      target: { value: "Atomic Habits" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    const cancelButton = await screen.findByRole("button", { name: "Cancel" });
    fireEvent.click(cancelButton);

    expect(cancelMutate).toHaveBeenCalledTimes(1);

    // Simulate the cancel mutation's onSuccess seeding the job cache with the
    // cancelled row — useJob's next read reflects that terminal state, and
    // JobStatus renders Cancelled instead of the spinner, with no dead end
    // (the search form above is still present to search again).
    mockUseJob.mockReturnValue({
      data: job({ status: "error", error_detail: "cancelled" }),
      isLoading: false,
    });
    rerender(<SearchPage />);

    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search a book title or ISBN")).toBeInTheDocument();
  });
});
