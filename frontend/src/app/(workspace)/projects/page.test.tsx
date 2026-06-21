import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useProjects } from "@/lib/hooks";
import type { ProjectOut } from "@/lib/types";
import ProjectsPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useProjects: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const mockUseProjects = useProjects as unknown as ReturnType<typeof vi.fn>;

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: "proj-1",
    name: "Stoicism & Philosophy",
    target_bisac: ["FIC044000"],
    subject_filter: {},
    config: {},
    seeded: true,
    work_count: 42,
    cluster_count: 7,
    created_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  mockUseProjects.mockReset();
});

describe("ProjectsPage", () => {
  it("renders a card per project for a non-empty list", () => {
    mockUseProjects.mockReturnValue({
      data: [
        project(),
        project({ id: "proj-2", name: "Cooking", target_bisac: ["CKB000000"] }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<ProjectsPage />);

    expect(screen.getByText("Stoicism & Philosophy")).toBeInTheDocument();
    expect(screen.getByText("Cooking")).toBeInTheDocument();
    expect(screen.getByText("FIC044000")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New project" })).toHaveAttribute(
      "href",
      "/projects/new",
    );
  });

  it("renders the onboarding empty state when the project list is empty", () => {
    mockUseProjects.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<ProjectsPage />);

    expect(
      screen.getAllByText("Create your first project").length,
    ).toBeGreaterThan(0);
    const cta = screen.getByRole("link", { name: "Create your first project" });
    expect(cta).toHaveAttribute("href", "/projects/new");
  });

  it("renders skeleton placeholders while loading", () => {
    mockUseProjects.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });

    const { container } = render(<ProjectsPage />);

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders an ErrorState with retry on error", () => {
    const refetch = vi.fn();
    mockUseProjects.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    });

    render(<ProjectsPage />);

    expect(screen.getByText("Couldn't load your projects.")).toBeInTheDocument();
    screen.getByRole("button", { name: /retry/i }).click();
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
