import { render, screen, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import type { CandidateOut } from "@/lib/types";
import { DemandSupply } from "./DemandSupply";

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
    platforms_used: ["hardcover"],
    incomplete: false,
    blind_spot: false,
    recent_supply_surge: false,
    ...overrides,
  };
}

describe("DemandSupply", () => {
  it("always renders the popularity-proxy disclaimer label", () => {
    render(<DemandSupply candidates={[candidate()]} />);

    expect(
      screen.getByText(/Demand is a popularity proxy/),
    ).toBeInTheDocument();
    expect(screen.getByText(/not sales or revenue/)).toBeInTheDocument();
  });

  it("renders a paired-bar row per candidate", () => {
    render(
      <DemandSupply
        candidates={[
          candidate({ ref_id: "a", title: "Effective Refactoring Patterns", demand_score: 0.8, supply_scarcity: 0.6 }),
          candidate({ ref_id: "b", title: "Legacy Migration Playbooks", demand_score: 0.4, supply_scarcity: 0.3 }),
        ]}
      />,
    );

    expect(screen.getByText("2 candidates")).toBeInTheDocument();

    // Recharts wraps long Y-axis tick labels across multiple <tspan> lines,
    // splitting the title into separate text nodes — so assert against the
    // chart's accessible row list (see DemandSupply.tsx) instead of the SVG
    // tick text. This is a real behavior assertion: one row per candidate,
    // each carrying its own demand/supply pair (not a shared/default value).
    // Scoped via data-testid since Recharts' <Legend> also renders a <ul><li>
    // list (the "Demand (proxy)" / "Supply scarcity" swatches) that would
    // otherwise collide with a plain getAllByRole("listitem") query.
    const rows = within(screen.getByTestId("demand-supply-rows")).getAllByRole(
      "listitem",
    );
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent(
      "Effective Refactoring Patterns: demand 0.80, supply scarcity 0.60",
    );
    expect(rows[1]).toHaveTextContent(
      "Legacy Migration Playbooks: demand 0.40, supply scarcity 0.30",
    );
  });

  it("renders an honest empty state instead of a blank box with zero candidates", () => {
    render(<DemandSupply candidates={[]} />);

    expect(screen.getByText("No candidates scored yet")).toBeInTheDocument();
    expect(screen.getByText(/Run a sweep/)).toBeInTheDocument();
    // Even the empty state still carries the proxy disclaimer? No — the
    // panel collapses to the empty note only; the disclaimer is part of the
    // populated view. Assert it is NOT duplicated/confusing here.
    expect(screen.queryByText("2 candidates")).not.toBeInTheDocument();
  });
});
