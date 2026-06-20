import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useJob } from "@/lib/hooks";
import type { JobOut } from "@/lib/types";
import { JobStatus } from "./JobStatus";

vi.mock("@/lib/hooks", () => ({
  useJob: vi.fn(),
}));

const mockUseJob = useJob as unknown as ReturnType<typeof vi.fn>;

function job(overrides: Partial<JobOut>): JobOut {
  return {
    id: "job-1",
    project_id: "proj-1",
    kind: "seed",
    status: "running",
    progress_pct: 0,
    step: null,
    counts: null,
    result_ref: null,
    error_detail: null,
    ...overrides,
  };
}

beforeEach(() => {
  mockUseJob.mockReset();
});

describe("JobStatus", () => {
  it("shows the step text and an accessible progressbar while running", () => {
    mockUseJob.mockReturnValue({
      data: job({ status: "running", progress_pct: 42, step: "clustering" }),
      isLoading: false,
    });

    render(<JobStatus jobId="job-1" variant="bar" />);

    expect(screen.getByText("clustering")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });

  it("shows a spinner + step inline for the inline variant", () => {
    mockUseJob.mockReturnValue({
      data: job({ status: "running", progress_pct: 10, step: "scanning meta…" }),
      isLoading: false,
    });

    render(<JobStatus jobId="job-1" variant="inline" />);

    expect(screen.getByText("scanning meta…")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "10");
  });

  it("shows error_detail and a Try again affordance on error", () => {
    const onRetry = vi.fn();
    mockUseJob.mockReturnValue({
      data: job({ status: "error", error_detail: "Hardcover API rate limit exceeded." }),
      isLoading: false,
    });

    render(<JobStatus jobId="job-1" onRetry={onRetry} />);

    expect(
      screen.getByText("Hardcover API rate limit exceeded."),
    ).toBeInTheDocument();
    const retry = screen.getByRole("button", { name: /try again/i });
    expect(retry).toBeInTheDocument();
  });

  it("renders error_detail of 'cancelled' as Cancelled, not a failure, with no retry", () => {
    mockUseJob.mockReturnValue({
      data: job({ status: "error", error_detail: "cancelled" }),
      isLoading: false,
    });

    render(<JobStatus jobId="job-1" onRetry={vi.fn()} />);

    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("calls onDone exactly once when the job reaches done", () => {
    const onDone = vi.fn();
    mockUseJob.mockReturnValue({
      data: job({ status: "done", progress_pct: 100 }),
      isLoading: false,
    });

    const { rerender } = render(<JobStatus jobId="job-1" onDone={onDone} />);
    rerender(<JobStatus jobId="job-1" onDone={onDone} />);
    rerender(<JobStatus jobId="job-1" onDone={onDone} />);

    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when jobId is null", () => {
    mockUseJob.mockReturnValue({ data: undefined, isLoading: false });
    const { container } = render(<JobStatus jobId={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
