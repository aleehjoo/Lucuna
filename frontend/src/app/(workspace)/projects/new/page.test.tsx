import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useCreateProject } from "@/lib/hooks";
import type { ProjectOut } from "@/lib/types";
import NewProjectPage from "./page";

vi.mock("@/lib/hooks", () => ({
  useCreateProject: vi.fn(),
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const mockUseCreateProject = useCreateProject as unknown as ReturnType<typeof vi.fn>;

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: "new-proj-1",
    name: "Programming",
    target_bisac: ["COM051000"],
    subject_filter: {},
    config: {},
    seeded: false,
    work_count: 0,
    cluster_count: 0,
    created_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  mockUseCreateProject.mockReset();
  push.mockReset();
});

describe("NewProjectPage", () => {
  it("submits a valid form: calls the create mutation with the right body and routes to the new dashboard", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(project());
    mockUseCreateProject.mockReturnValue({ mutateAsync, isPending: false });

    render(<NewProjectPage />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Programming" },
    });
    fireEvent.click(screen.getByTitle("Programming / General"));
    fireEvent.change(screen.getByLabelText(/Keywords/), {
      target: { value: "python, async" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    await vi.waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        name: "Programming",
        target_bisac: ["COM051000"],
        subject_filter: { keywords: ["python", "async"] },
        config: { timely_evergreen: 0.5 },
      });
    });

    await vi.waitFor(() => {
      expect(push).toHaveBeenCalledWith("/p/new-proj-1/dashboard");
    });
  });

  it("blocks submit and shows a validation message when name is empty", () => {
    const mutateAsync = vi.fn();
    mockUseCreateProject.mockReturnValue({ mutateAsync, isPending: false });

    render(<NewProjectPage />);

    fireEvent.click(screen.getByTitle("Programming / General"));
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(screen.getByText("Name the project before creating it.")).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("blocks submit and shows a validation message when no BISAC code is selected", () => {
    const mutateAsync = vi.fn();
    mockUseCreateProject.mockReturnValue({ mutateAsync, isPending: false });

    render(<NewProjectPage />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Programming" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(screen.getByText("Select at least one BISAC code.")).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("states that creating a project does not auto-seed it", () => {
    mockUseCreateProject.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    render(<NewProjectPage />);

    expect(screen.getByText(/does not seed it/i)).toBeInTheDocument();
  });

  it("shows the backend error detail inline on a failed submit", async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error("name already in use"));
    mockUseCreateProject.mockReturnValue({ mutateAsync, isPending: false });

    render(<NewProjectPage />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Programming" },
    });
    fireEvent.click(screen.getByTitle("Programming / General"));
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    await vi.waitFor(() => {
      expect(screen.getByText("name already in use")).toBeInTheDocument();
    });
    expect(push).not.toHaveBeenCalled();
  });
});
