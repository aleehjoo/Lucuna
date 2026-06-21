import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api";
import { useWork } from "@/lib/hooks";
import type { ClusterOut, WorkDetailOut } from "@/lib/types";
import WorkDetailPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useWork: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "proj-1", workId: "work-1" }),
}));

const mockUseWork = useWork as unknown as ReturnType<typeof vi.fn>;

function cluster(overrides: Partial<ClusterOut> = {}): ClusterOut {
  return {
    id: "cluster-1",
    label: "Outdated examples",
    representative: "The code samples feel dated for modern tooling.",
    member_count: 5,
    reviewer_count: 5,
    helpful_weight: 3.2,
    platforms: ["hardcover"],
    cross_platform: false,
    work_id: "work-1",
    bisac_code: "COM051000",
    ...overrides,
  };
}

function workDetail(overrides: Partial<WorkDetailOut> = {}): WorkDetailOut {
  return {
    id: "work-1",
    title: "Clean Code",
    author: "Robert C. Martin",
    agg_rating_avg: 4.2,
    agg_rating_count: 1200,
    review_count: 40,
    clusters: [],
    ...overrides,
  };
}

function setMock({
  data,
  isLoading = false,
  isError = false,
  error,
  refetch = vi.fn(),
}: {
  data?: WorkDetailOut;
  isLoading?: boolean;
  isError?: boolean;
  error?: Error;
  refetch?: ReturnType<typeof vi.fn>;
}) {
  mockUseWork.mockReturnValue({ data, isLoading, isError, error, refetch });
}

beforeEach(() => {
  mockUseWork.mockReset();
});

describe("WorkDetailPage", () => {
  it("renders title, author, rating, and clusters", () => {
    setMock({
      data: workDetail({
        clusters: [
          cluster(),
          cluster({ id: "c2", label: "Missing exercises", representative: "No practice problems." }),
          cluster({ id: "c3", label: "Pacing issues", representative: "Moves too fast." }),
        ],
      }),
    });

    render(<WorkDetailPage />);

    expect(screen.getByText("Clean Code")).toBeInTheDocument();
    expect(screen.getByText("Robert C. Martin")).toBeInTheDocument();
    expect(screen.getByText("4.2")).toBeInTheDocument();
    expect(screen.getByText(/from 1200 rated review/)).toBeInTheDocument();
    expect(screen.getByText(/40 reviews total/)).toBeInTheDocument();
    expect(screen.getByText("Outdated examples")).toBeInTheDocument();
    expect(screen.getByText("Missing exercises")).toBeInTheDocument();
    expect(screen.getByText("Pacing issues")).toBeInTheDocument();
    expect(screen.queryByText("Low signal")).not.toBeInTheDocument();

    const backLink = screen.getByRole("link", { name: /Back to Niche Dashboard/ });
    expect(backLink).toHaveAttribute("href", "/p/proj-1/dashboard");
  });

  it('shows "No rating" honestly when agg_rating_avg is null', () => {
    setMock({
      data: workDetail({ agg_rating_avg: null, agg_rating_count: null, clusters: [cluster()] }),
    });

    render(<WorkDetailPage />);

    expect(screen.getByText("No rating")).toBeInTheDocument();
    expect(screen.queryByText(/rated review/)).not.toBeInTheDocument();
  });

  it("renders a low_signal note and still shows rating/provenance when there are 0 clusters", () => {
    setMock({ data: workDetail({ clusters: [] }) });

    render(<WorkDetailPage />);

    expect(screen.getByText("Low signal")).toBeInTheDocument();
    expect(screen.getByText(/no distinct complaint clusters/)).toBeInTheDocument();
    // Rating/provenance must still be present — never a blank panel.
    expect(screen.getByText("4.2")).toBeInTheDocument();
    expect(screen.getByText(/40 reviews total/)).toBeInTheDocument();
  });

  it("renders a low_signal note when there is exactly one cluster", () => {
    setMock({ data: workDetail({ clusters: [cluster()] }) });

    render(<WorkDetailPage />);

    expect(screen.getByText("Low signal")).toBeInTheDocument();
    expect(screen.getByText("Outdated examples")).toBeInTheDocument();
  });

  it("renders a low_signal note when every cluster shares one label", () => {
    setMock({
      data: workDetail({
        clusters: [cluster({ id: "c1" }), cluster({ id: "c2" }), cluster({ id: "c3" })],
      }),
    });

    render(<WorkDetailPage />);

    expect(screen.getByText("Low signal")).toBeInTheDocument();
  });

  it("renders skeleton placeholders while loading", () => {
    setMock({ isLoading: true });

    const { container } = render(<WorkDetailPage />);

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders the not-found EmptyState (not a raw error) on a 404", () => {
    setMock({
      isError: true,
      error: new ApiError("work not found", 404),
    });

    render(<WorkDetailPage />);

    expect(screen.getByText("That title isn't in this project")).toBeInTheDocument();
    const dashboardLink = screen.getByRole("link", { name: "Back to Niche Dashboard" });
    expect(dashboardLink).toHaveAttribute("href", "/p/proj-1/dashboard");
  });

  it("renders an ErrorState with retry on a non-404 error", () => {
    const refetch = vi.fn();
    setMock({
      isError: true,
      error: new ApiError("Request failed: 500", 500),
      refetch,
    });

    render(<WorkDetailPage />);

    expect(screen.getByText("Couldn't load this work.")).toBeInTheDocument();
    const retryButton = screen.getByRole("button", { name: /retry/i });
    expect(retryButton).toBeInTheDocument();
  });
});
