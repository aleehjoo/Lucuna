import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useJob, useProjectJobs, useStartSeed } from "@/lib/hooks";
import type { JobOut } from "@/lib/types";
import SeedPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useStartSeed: vi.fn(),
  useProjectJobs: vi.fn(),
  useJob: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "proj-1" }),
}));

const mockUseStartSeed = useStartSeed as unknown as ReturnType<typeof vi.fn>;
const mockUseProjectJobs = useProjectJobs as unknown as ReturnType<typeof vi.fn>;
const mockUseJob = useJob as unknown as ReturnType<typeof vi.fn>;

function job(overrides: Partial<JobOut> = {}): JobOut {
  return {
    id: "job-1",
    project_id: "proj-1",
    kind: "seed",
    status: "running",
    progress_pct: 10,
    step: "scanning meta 50k/200k",
    counts: null,
    result_ref: null,
    error_detail: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:05:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  mockUseStartSeed.mockReset();
  mockUseProjectJobs.mockReset();
  mockUseJob.mockReset();
  mockUseProjectJobs.mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
  mockUseJob.mockReturnValue({ data: undefined, isLoading: false });
});

describe("SeedPage", () => {
  it("shows the long-operation warning", () => {
    mockUseStartSeed.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<SeedPage />);

    expect(screen.getByText(/about 1 hour/)).toBeInTheDocument();
    expect(screen.getByText(/navigate away/)).toBeInTheDocument();
  });

  it("renders default values for meta_limit, review_limit, max_works", () => {
    mockUseStartSeed.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<SeedPage />);

    expect(screen.getByLabelText("Meta limit")).toHaveValue(200000);
    expect(screen.getByLabelText("Review limit")).toHaveValue(1000000);
    expect(screen.getByLabelText("Max works")).toHaveValue(25);
  });

  it("calls the start-seed mutation with the current input values", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ job_id: "job-1" });
    mockUseStartSeed.mockReturnValue({ mutateAsync, isPending: false });

    render(<SeedPage />);

    fireEvent.change(screen.getByLabelText("Meta limit"), {
      target: { value: "50000" },
    });
    fireEvent.change(screen.getByLabelText("Review limit"), {
      target: { value: "250000" },
    });
    fireEvent.change(screen.getByLabelText("Max works"), {
      target: { value: "10" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Start seed" }));

    await vi.waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        meta_limit: 50000,
        review_limit: 250000,
        max_works: 10,
      });
    });
  });

  it("renders the %/step progress bar once a seed job is started", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ job_id: "job-1" });
    mockUseStartSeed.mockReturnValue({ mutateAsync, isPending: false });
    mockUseJob.mockReturnValue({ data: job(), isLoading: false });

    render(<SeedPage />);

    fireEvent.click(screen.getByRole("button", { name: "Start seed" }));

    await vi.waitFor(() => {
      expect(mutateAsync).toHaveBeenCalled();
      expect(screen.getByText("scanning meta 50k/200k")).toBeInTheDocument();
      const bar = screen.getByRole("progressbar");
      expect(bar).toHaveAttribute("aria-valuenow", "10");
    });
  });

  it("auto-resumes an in-flight seed job found on mount", () => {
    mockUseStartSeed.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    mockUseProjectJobs.mockReturnValue({
      data: [job({ id: "job-resume", status: "running", progress_pct: 64, step: "clustering" })],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseJob.mockReturnValue({
      data: job({ id: "job-resume", status: "running", progress_pct: 64, step: "clustering" }),
      isLoading: false,
    });

    render(<SeedPage />);

    // The progress bar renders immediately, without clicking "Start seed" —
    // this is the navigate-away-and-back case: the job survives because it's
    // tracked by job id (useJob), not transient component state.
    expect(screen.getByText("clustering")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "64");
    expect(screen.getByText(/Resumed an in-progress seed/)).toBeInTheDocument();
  });

  it("does not auto-resume a finished seed job", () => {
    mockUseStartSeed.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    mockUseProjectJobs.mockReturnValue({
      data: [job({ id: "job-done", status: "done", progress_pct: 100 })],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<SeedPage />);

    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("renders the past seed-jobs list, including error detail", () => {
    mockUseStartSeed.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    mockUseProjectJobs.mockReturnValue({
      data: [
        job({ id: "job-a", status: "done", progress_pct: 100, counts: { works: 25, reviews: 480000 } }),
        job({ id: "job-b", status: "error", error_detail: "Hardcover API rate limit exceeded." }),
        { ...job({ id: "job-c" }), kind: "sweep" }, // not a seed job — filtered out
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<SeedPage />);

    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(
      screen.getByText("Hardcover API rate limit exceeded."),
    ).toBeInTheDocument();
    expect(screen.getByText(/works:/)).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
  });

  it("renders an empty state when there are no past seed jobs", () => {
    mockUseStartSeed.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<SeedPage />);

    expect(screen.getByText("No seed jobs yet")).toBeInTheDocument();
  });

  it("renders skeleton placeholders while past jobs are loading", () => {
    mockUseStartSeed.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    mockUseProjectJobs.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });

    const { container } = render(<SeedPage />);

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders an ErrorState with retry when past jobs fail to load", () => {
    const refetch = vi.fn();
    mockUseStartSeed.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    mockUseProjectJobs.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    });

    render(<SeedPage />);

    expect(screen.getByText("Couldn't load past seed jobs.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it("shows a start-seed error message when the mutation rejects", async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error("Seed already running."));
    mockUseStartSeed.mockReturnValue({ mutateAsync, isPending: false });

    render(<SeedPage />);

    fireEvent.click(screen.getByRole("button", { name: "Start seed" }));

    await vi.waitFor(() => {
      expect(screen.getByText("Seed already running.")).toBeInTheDocument();
    });
  });
});
