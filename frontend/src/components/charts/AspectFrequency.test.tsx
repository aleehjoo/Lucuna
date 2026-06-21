import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import type { ClusterOut } from "@/lib/types";
import { AspectFrequency } from "./AspectFrequency";

function cluster(overrides: Partial<ClusterOut> = {}): ClusterOut {
  return {
    id: "cluster-1",
    label: "Outdated examples",
    representative: "The code samples feel dated.",
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

describe("AspectFrequency", () => {
  it("renders one bar per cluster, ranked by reviewer_count, with provenance", () => {
    render(
      <AspectFrequency
        clusters={[
          cluster({ id: "a", label: "Outdated examples", reviewer_count: 5 }),
          cluster({ id: "b", label: "Missing exercises", reviewer_count: 18 }),
        ]}
      />,
    );

    expect(screen.getByText("What readers complain about")).toBeInTheDocument();
    expect(screen.getByText("2 aspects · 23 reviewers")).toBeInTheDocument();

    // Recharts wraps long Y-axis tick labels across multiple <tspan> lines,
    // splitting the name into separate text nodes — so assert against the
    // chart's accessible row list (see AspectFrequency.tsx) instead of the
    // SVG tick text. This is a real behavior assertion: one row per
    // cluster, ranked by reviewer_count descending (higher count first),
    // each carrying its reviewer count.
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Missing exercises: 18 reviewers");
    expect(rows[1]).toHaveTextContent("Outdated examples: 5 reviewers");
  });

  it("renders an honest empty state instead of a blank box with zero clusters", () => {
    render(<AspectFrequency clusters={[]} />);

    expect(screen.getByText("No complaint clusters yet")).toBeInTheDocument();
    expect(screen.getByText(/interpret this niche as thin/)).toBeInTheDocument();
  });
});
