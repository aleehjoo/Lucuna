import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useProject, useUpdateProject } from "@/lib/hooks";
import type { ProjectOut } from "@/lib/types";
import SettingsPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useProject: vi.fn(),
  useUpdateProject: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "proj-1" }),
}));

const mockUseProject = useProject as unknown as ReturnType<typeof vi.fn>;
const mockUseUpdateProject = useUpdateProject as unknown as ReturnType<typeof vi.fn>;

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: "proj-1",
    name: "Programming",
    target_bisac: ["COM051000"],
    subject_filter: {},
    config: {},
    seeded: true,
    work_count: 6,
    cluster_count: 2,
    created_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  mockUseProject.mockReset();
  mockUseUpdateProject.mockReset();
});

describe("SettingsPage", () => {
  it("loads current config values, with defaults filling in anything unset", () => {
    mockUseProject.mockReturnValue({
      data: project({ config: { timely_evergreen: 0.8 } }),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseUpdateProject.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<SettingsPage />);

    // The slider reflects the saved value (0.8), not the default (0.5).
    expect(screen.getByLabelText(/Timely ↔ evergreen/i)).toHaveValue("0.8");
    // Unset knobs fall back to sensible defaults rather than blank/zero.
    expect(screen.getByLabelText(/Recency window/i)).toHaveValue(24);
    expect(screen.getByLabelText(/Export max candidates/i)).toHaveValue(20);
    expect(screen.getByLabelText(/Export token budget/i)).toHaveValue(8000);
  });

  it("saving sends a PUT (via useUpdateProject) with the intent-knob values in config", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(project());
    mockUseProject.mockReturnValue({
      data: project({ config: { timely_evergreen: 0.5 } }),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseUpdateProject.mockReturnValue({ mutateAsync, isPending: false });

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText(/Timely ↔ evergreen/i), {
      target: { value: "0.9" },
    });
    fireEvent.change(screen.getByLabelText(/Recency window/i), {
      target: { value: "12" },
    });
    fireEvent.change(screen.getByLabelText(/Export max candidates/i), {
      target: { value: "30" },
    });
    fireEvent.change(screen.getByLabelText(/Export token budget/i), {
      target: { value: "5000" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Save settings/i }));

    await vi.waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        config: {
          timely_evergreen: 0.9,
          recency_months: 12,
          export_max_candidates: 30,
          export_token_budget: 5000,
        },
      });
    });

    expect(await screen.findByText(/Settings saved/i)).toBeInTheDocument();
  });

  it("shows an inline error when the save fails", async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error("server exploded"));
    mockUseProject.mockReturnValue({
      data: project(),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseUpdateProject.mockReturnValue({ mutateAsync, isPending: false });

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole("button", { name: /Save settings/i }));

    expect(await screen.findByText("server exploded")).toBeInTheDocument();
  });

  it("renders a loading skeleton while the project is loading", () => {
    mockUseProject.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseUpdateProject.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    const { container } = render(<SettingsPage />);

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders an ErrorState with retry when the project fails to load", () => {
    const refetch = vi.fn();
    mockUseProject.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    });
    mockUseUpdateProject.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<SettingsPage />);

    expect(screen.getByText("Couldn't load project settings.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalled();
  });

  // GUARD (Frontend PRD §13.10 / acceptance §9): correctness knobs must NEVER
  // appear in the Settings UI — they live only in advanced.yaml. Exposing any
  // of these lets an operator manufacture whatever gap_score they want, which
  // defeats the entire point of a validity-gated score. This test fails loud
  // if anyone ever adds one of these fields to the Settings form.
  it("GUARD: never renders any correctness-knob name anywhere in the Settings UI", () => {
    mockUseProject.mockReturnValue({
      data: project({
        config: {
          timely_evergreen: 0.5,
          recency_months: 24,
          export_max_candidates: 20,
          export_token_budget: 8000,
        },
      }),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseUpdateProject.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    const { container } = render(<SettingsPage />);
    const rendered = container.textContent ?? "";
    const renderedHtml = container.innerHTML;

    const forbidden = [
      "min_critical_per_work",
      "shrinkage",
      "epsilon",
      "normalization",
      "revision",
      "crosswalk",
    ];

    for (const term of forbidden) {
      expect(rendered.toLowerCase()).not.toContain(term.toLowerCase());
      expect(renderedHtml.toLowerCase()).not.toContain(term.toLowerCase());
    }
  });
});
