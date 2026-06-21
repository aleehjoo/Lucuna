import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useCancelJob, useCandidates, useJob, useStartSweep } from "@/lib/hooks";
import type { CandidateOut, JobOut } from "@/lib/types";
import CategorySweepPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useCandidates: vi.fn(),
  useStartSweep: vi.fn(),
  useJob: vi.fn(),
  useCancelJob: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "proj-1" }),
}));

const mockUseCandidates = useCandidates as unknown as ReturnType<typeof vi.fn>;
const mockUseStartSweep = useStartSweep as unknown as ReturnType<typeof vi.fn>;
const mockUseJob = useJob as unknown as ReturnType<typeof vi.fn>;
const mockUseCancelJob = useCancelJob as unknown as ReturnType<typeof vi.fn>;

function candidate(overrides: Partial<CandidateOut> = {}): CandidateOut {
  return {
    scope: "bisac",
    ref_id: "COM051000",
    title: "Effective Refactoring Patterns",
    gap_score: 0.72,
    demand_score: 0.8,
    supply_scarcity: 0.6,
    unmet_need: 0.7,
    confidence: 0.65,
    sample_size: 40,
    platforms_used: ["hardcover", "goodreads"],
    incomplete: false,
    blind_spot: false,
    recent_supply_surge: false,
    ...overrides,
  };
}

function job(overrides: Partial<JobOut> = {}): JobOut {
  return {
    id: "job-1",
    project_id: "proj-1",
    kind: "sweep",
    status: "running",
    progress_pct: 10,
    step: "scoring",
    counts: null,
    result_ref: null,
    error_detail: null,
    ...overrides,
  };
}

beforeEach(() => {
  mockUseCandidates.mockReset();
  mockUseStartSweep.mockReset();
  mockUseJob.mockReset();
  mockUseJob.mockReturnValue({ data: undefined, isLoading: false });
  mockUseCancelJob.mockReset();
  mockUseCancelJob.mockReturnValue({ mutate: vi.fn(), isPending: false });
});

describe("CategorySweepPage", () => {
  it("shows the advanced-mode banner", () => {
    mockUseCandidates.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseStartSweep.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<CategorySweepPage />);

    expect(screen.getByText(/Advanced view/)).toBeInTheDocument();
  });

  it("renders ranked candidates descending by gap_score", () => {
    mockUseCandidates.mockReturnValue({
      data: [
        candidate({ ref_id: "a", title: "Lower Gap", gap_score: 0.3 }),
        candidate({ ref_id: "b", title: "Higher Gap", gap_score: 0.9 }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseStartSweep.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    const { container } = render(<CategorySweepPage />);

    // Scoped to the ranked <ol> itself — GapStrip/DemandSupply below it
    // also render each candidate's title (accessible row list + axis
    // ticks), which is real, intentional duplication, not a bug to assert
    // against here.
    const rankedList = container.querySelector("ol") as HTMLElement;
    const titles = within(rankedList)
      .getAllByText(/Higher Gap|Lower Gap/)
      .map((el) => el.textContent);
    expect(titles).toEqual(["Higher Gap", "Lower Gap"]);
    expect(within(rankedList).getByText("0.90")).toBeInTheDocument();
    expect(within(rankedList).getByText("0.30")).toBeInTheDocument();
  });

  it("expanding a row reveals its flags, platforms, and component figures", () => {
    mockUseCandidates.mockReturnValue({
      data: [
        candidate({
          ref_id: "a",
          title: "Thin Signal Niche",
          incomplete: true,
          blind_spot: true,
          confidence: 0.2,
          platforms_used: ["hardcover"],
        }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseStartSweep.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<CategorySweepPage />);

    // Flags are visible even collapsed.
    expect(screen.getByText("Incomplete")).toBeInTheDocument();
    expect(screen.getByText("Blind spot")).toBeInTheDocument();

    // "Thin Signal Niche" also appears in GapStrip/DemandSupply's accessible
    // row lists below the ranked list — real, intentional duplication of
    // the same data, not a bug. The candidate row itself is always the
    // first match (it renders first, inside the ranked <ol>).
    // "Thin Signal Niche" also appears in GapStrip/DemandSupply's accessible
    // row lists below the ranked list, and Recharts appends a hidden, reused
    // `recharts_measurement_span` directly to `document.body` for text-width
    // measurement (a singleton that can hold a previous render's text) — so
    // find the actual candidate row by its `<li>` ancestor rather than
    // assuming array order.
    const row = screen
      .getAllByText("Thin Signal Niche")
      .map((el) => el.closest("li"))
      .find((li): li is HTMLLIElement => li !== null) as HTMLElement;
    const toggle = within(row).getByRole("button");
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    // Provenance/figures not yet shown.
    expect(within(row).queryByText("Demand")).not.toBeInTheDocument();

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(within(row).getByText("Demand")).toBeInTheDocument();
    expect(within(row).getByText("Supply scarcity")).toBeInTheDocument();
    expect(within(row).getByText("Unmet need")).toBeInTheDocument();
    expect(within(row).getByText("hardcover")).toBeInTheDocument();
    expect(within(row).getByText(/Low confidence/)).toBeInTheDocument();
  });

  it("shows only bisac-scope candidates when the list has both scopes", () => {
    mockUseCandidates.mockReturnValue({
      data: [
        candidate({ scope: "work", ref_id: "work-1", title: "Per-Work Gap", gap_score: 0.5 }),
        candidate({ scope: "bisac", ref_id: "COM051000", title: "Category Gap", gap_score: 0.9 }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseStartSweep.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<CategorySweepPage />);

    // "Category Gap" also appears in GapStrip/DemandSupply's accessible row
    // lists below the ranked list — real, intentional duplication of the
    // same (already bisac-filtered) data, not a bug.
    expect(screen.getAllByText("Category Gap").length).toBeGreaterThan(0);
    expect(screen.queryByText("Per-Work Gap")).not.toBeInTheDocument();
    // "1 candidate" also appears as GapStrip's own provenance label below
    // the ranked list — both are real, intentional renderings of the same
    // (already bisac-filtered) count.
    expect(screen.getAllByText("1 candidate").length).toBeGreaterThan(0);
  });

  it("renders an empty state with no candidates", () => {
    mockUseCandidates.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseStartSweep.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<CategorySweepPage />);

    expect(screen.getByText("No gap candidates yet")).toBeInTheDocument();
    expect(screen.getByText(/Run a sweep to score/)).toBeInTheDocument();
  });

  it("renders skeleton placeholders while loading", () => {
    mockUseCandidates.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseStartSweep.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    const { container } = render(<CategorySweepPage />);

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders an ErrorState with retry on candidates error", () => {
    const refetch = vi.fn();
    mockUseCandidates.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    });
    mockUseStartSweep.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<CategorySweepPage />);

    expect(screen.getByText("Couldn't load gap candidates.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it("triggers the sweep mutation and shows job progress when Run Sweep is clicked", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ job_id: "job-1" });
    mockUseCandidates.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseStartSweep.mockReturnValue({ mutateAsync, isPending: false });
    mockUseJob.mockReturnValue({ data: job(), isLoading: false });

    render(<CategorySweepPage />);

    fireEvent.click(screen.getByRole("button", { name: "Run Sweep" }));

    await vi.waitFor(() => {
      expect(mutateAsync).toHaveBeenCalled();
      expect(screen.getByText("scoring")).toBeInTheDocument();
    });
  });
});
