import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useJob, useStartSearch } from "@/lib/hooks";
import type { JobOut, LiveSearchCounts } from "@/lib/types";
import SearchPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useStartSearch: vi.fn(),
  useJob: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "proj-1" }),
}));

const mockUseStartSearch = useStartSearch as unknown as ReturnType<typeof vi.fn>;
const mockUseJob = useJob as unknown as ReturnType<typeof vi.fn>;

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
});
