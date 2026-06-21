import { render, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import type { CandidateOut } from "@/lib/types";
import { GapStrip } from "./GapStrip";

function candidate(overrides: Partial<CandidateOut> = {}): CandidateOut {
  return {
    scope: "bisac",
    ref_id: "COM051000",
    title: "Effective Refactoring Patterns",
    gap_score: 0,
    demand_score: 0,
    supply_scarcity: 0,
    unmet_need: 0,
    confidence: 0.2,
    sample_size: 13,
    platforms_used: ["hardcover"],
    incomplete: true,
    blind_spot: false,
    recent_supply_surge: false,
    ...overrides,
  };
}

describe("GapStrip", () => {
  it("(variation branch) renders a bar per candidate with its gap% label when gap_scores vary", () => {
    const { container } = render(
      <GapStrip
        candidates={[
          candidate({ ref_id: "a", title: "Effective Refactoring Patterns", gap_score: 0.72, confidence: 0.65 }),
          candidate({ ref_id: "b", title: "Legacy Migration Playbooks", gap_score: 0, confidence: 0.2 }),
        ]}
      />,
    );
    const screen = within(container);

    // Real bars, not the degenerate note.
    expect(
      screen.queryByText(/Gap scores need demand signals/),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Gap map")).toBeInTheDocument();
    expect(screen.getByText("2 candidates")).toBeInTheDocument();

    // The SVG gap% label is rendered as a <text> split into separate "NN"
    // and "% gap" text nodes (SVG/Recharts text layout) and the Y-axis tick
    // can likewise wrap a long title across multiple <tspan> lines — neither
    // is reliably readable as one exact string (by jsdom OR a screen
    // reader). Assert against the chart's accessible row list (see
    // GapStrip.tsx) instead: this is a real behavior assertion that each
    // candidate gets its own row with its own gap% label, not a tautology.
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Effective Refactoring Patterns: 72% gap");
    // The 0%-gap candidate (a genuine zero, per PRD §10) still renders a row
    // with its own label — a real zero propagates and is shown, not hidden
    // or dropped from the chart (only an ALL-zero set triggers the degenerate
    // note; a mix of real values, including a true zero, renders as bars).
    expect(rows[1]).toHaveTextContent("Legacy Migration Playbooks: 0% gap");
  });

  it("(degenerate branch) renders an intentional honest note — NOT zero-height bars — when every gap_score is ~0", () => {
    const { container } = render(
      <GapStrip
        candidates={[
          candidate({ ref_id: "a", title: "Effective Refactoring Patterns", gap_score: 0 }),
          candidate({ ref_id: "b", title: "Legacy Migration Playbooks", gap_score: 0 }),
        ]}
      />,
    );
    const screen = within(container);

    // The exact, deliberate copy — not a generic "no data" placeholder.
    expect(screen.getByText("Gap map not yet populated")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Gap scores need demand signals, which aren't present in a $0 corpus-only run. Seed demand sources (or run a live search) to populate the gap map.",
      ),
    ).toBeInTheDocument();

    // No bar chart content at all — never a row of invisible/zero-width bars
    // that could be mistaken for "zero opportunity here." Scoped to this
    // render's container (not the global `screen`) because Recharts appends
    // a hidden, reused `recharts_measurement_span` directly to
    // `document.body` for text-width measurement; that singleton can still
    // hold a previous test's label text in document.body and would produce
    // a false-positive match against the global screen.
    expect(screen.queryByText("Effective Refactoring Patterns")).not.toBeInTheDocument();
    expect(screen.queryByText("Legacy Migration Playbooks")).not.toBeInTheDocument();
    expect(screen.queryByText(/% gap/)).not.toBeInTheDocument();
    expect(screen.queryByText("2 candidates")).not.toBeInTheDocument();
  });

  it("renders an honest empty state (not the degenerate note) when there are zero candidates at all", () => {
    const { container } = render(<GapStrip candidates={[]} />);
    const screen = within(container);

    expect(screen.getByText("No gap candidates yet")).toBeInTheDocument();
    expect(
      screen.queryByText(/Gap scores need demand signals/),
    ).not.toBeInTheDocument();
  });
});
