import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useCandidates, useClusters, useProject, useWorks } from "@/lib/hooks";
import type { CandidateOut, ClusterOut, ProjectOut, WorkOut } from "@/lib/types";
import DashboardPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useProject: vi.fn(),
  useWorks: vi.fn(),
  useClusters: vi.fn(),
  useCandidates: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "proj-1" }),
}));

const mockUseProject = useProject as unknown as ReturnType<typeof vi.fn>;
const mockUseWorks = useWorks as unknown as ReturnType<typeof vi.fn>;
const mockUseClusters = useClusters as unknown as ReturnType<typeof vi.fn>;
const mockUseCandidates = useCandidates as unknown as ReturnType<typeof vi.fn>;

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: "proj-1",
    name: "Example - Programming & Software Books",
    target_bisac: ["COM051000"],
    subject_filter: {},
    seeded: true,
    work_count: 6,
    cluster_count: 2,
    created_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

function work(overrides: Partial<WorkOut> = {}): WorkOut {
  return {
    id: "work-1",
    title: "Clean Code",
    author: "Robert C. Martin",
    agg_rating_avg: 4.2,
    agg_rating_count: 1200,
    review_count: 40,
    ...overrides,
  };
}

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
    work_id: null,
    bisac_code: "COM051000",
    ...overrides,
  };
}

function candidate(overrides: Partial<CandidateOut> = {}): CandidateOut {
  return {
    scope: "work",
    ref_id: "work-1",
    title: "Clean Code",
    gap_score: 0.72,
    demand_score: 0.8,
    supply_scarcity: 0.6,
    unmet_need: 0.7,
    confidence: 0.65,
    sample_size: 40,
    platforms_used: ["hardcover"],
    incomplete: false,
    blind_spot: false,
    recent_supply_surge: false,
    ...overrides,
  };
}

function setMocks({
  project: projectData,
  works,
  clusters,
  candidates,
  loading = false,
  error = false,
}: {
  project?: ProjectOut;
  works?: WorkOut[];
  clusters?: ClusterOut[];
  candidates?: CandidateOut[];
  loading?: boolean;
  error?: boolean;
}) {
  const refetch = vi.fn();
  mockUseProject.mockReturnValue({
    data: projectData,
    isLoading: loading,
    isError: error,
    refetch,
  });
  mockUseWorks.mockReturnValue({
    data: works,
    isLoading: loading,
    isError: error,
    refetch,
  });
  mockUseClusters.mockReturnValue({
    data: clusters,
    isLoading: loading,
    isError: error,
    refetch,
  });
  mockUseCandidates.mockReturnValue({
    data: candidates,
    isLoading: loading,
    isError: error,
    refetch,
  });
}

beforeEach(() => {
  mockUseProject.mockReset();
  mockUseWorks.mockReset();
  mockUseClusters.mockReset();
  mockUseCandidates.mockReset();
});

describe("DashboardPage", () => {
  it("renders works, clusters, and candidates for a seeded project", () => {
    setMocks({
      project: project(),
      works: [
        work(),
        work({ id: "work-2", title: "The Pragmatic Programmer", author: "David Thomas" }),
      ],
      clusters: [
        cluster(),
        cluster({ id: "cluster-2", label: "Missing exercises", representative: "No practice problems." }),
        cluster({ id: "cluster-3", label: "Pacing issues", representative: "Moves too fast in places." }),
      ],
      candidates: [candidate()],
    });

    render(<DashboardPage />);

    // KPIs
    expect(screen.getAllByText("Works").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Reviews").length).toBeGreaterThan(0);
    expect(screen.getByText("Clusters")).toBeInTheDocument();
    expect(screen.getAllByText("Gap candidates").length).toBeGreaterThan(0);

    // Works table
    expect(screen.getAllByText("Clean Code").length).toBeGreaterThan(0);
    expect(screen.getByText("The Pragmatic Programmer")).toBeInTheDocument();
    expect(screen.getByText("Robert C. Martin")).toBeInTheDocument();

    // Clusters (3 distinct labels, > 2 clusters -> not low signal)
    expect(screen.getByText("Outdated examples")).toBeInTheDocument();
    expect(screen.getByText("Missing exercises")).toBeInTheDocument();
    expect(screen.queryByText("Low signal")).not.toBeInTheDocument();

    // Candidates
    expect(screen.getAllByText("Clean Code").length).toBeGreaterThan(0);
    expect(screen.getByText("0.72")).toBeInTheDocument();
  });

  it("renders the empty state when the project is not seeded", () => {
    setMocks({
      project: project({ seeded: false, work_count: 0 }),
      works: [],
      clusters: [],
      candidates: [],
    });

    render(<DashboardPage />);

    expect(
      screen.getByText(/Seed this niche to unlock historical depth/),
    ).toBeInTheDocument();
    const seedLink = screen.getByRole("link", { name: "Seed & Data" });
    expect(seedLink).toHaveAttribute("href", "/p/proj-1/seed");
    const searchLink = screen.getByRole("link", { name: "Search a title live" });
    expect(searchLink).toHaveAttribute("href", "/p/proj-1/search");
  });

  it("renders the empty state when seeded but there are zero works", () => {
    setMocks({
      project: project({ seeded: true, work_count: 0 }),
      works: [],
      clusters: [],
      candidates: [],
    });

    render(<DashboardPage />);

    expect(
      screen.getByText(/Seed this niche to unlock historical depth/),
    ).toBeInTheDocument();
  });

  it("renders a low_signal note when clusters are sparse or degenerate", () => {
    setMocks({
      project: project(),
      works: [work()],
      clusters: [cluster()],
      candidates: [],
    });

    render(<DashboardPage />);

    expect(screen.getByText("Low signal")).toBeInTheDocument();
    expect(screen.getByText(/low signal: 1 cluster/)).toBeInTheDocument();
  });

  it("renders a low_signal note when every cluster shares one label", () => {
    setMocks({
      project: project(),
      works: [work()],
      clusters: [
        cluster({ id: "c1" }),
        cluster({ id: "c2" }),
        cluster({ id: "c3" }),
      ],
      candidates: [],
    });

    render(<DashboardPage />);

    expect(screen.getByText("Low signal")).toBeInTheDocument();
    expect(screen.getByText(/all one label/)).toBeInTheDocument();
  });

  it("renders skeleton placeholders while loading", () => {
    setMocks({ loading: true });

    const { container } = render(<DashboardPage />);

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders an ErrorState with retry on error", () => {
    setMocks({ error: true });

    render(<DashboardPage />);

    expect(
      screen.getByText("Couldn't load this project's dashboard."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
