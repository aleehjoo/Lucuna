import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import type { ContextPack, LiveSearchCounts } from "@/lib/types";
import { SearchResult } from "./SearchResult";

function pack(overrides: Partial<ContextPack["candidates"][0]> = {}): ContextPack {
  return {
    legend: {},
    instructions_to_model: {},
    known_limitations: {},
    target: { project: "Atomic Habits", bisac: [], mode: "single_title" },
    generated_at: "2026-06-20T00:00:00Z",
    provenance: {
      platforms_used: ["hardcover"],
      total_reviews: 13,
      cross_platform_agreement_pct: 0,
    },
    candidates: [
      {
        ref: "work",
        title_or_subject: "Atomic Habits",
        gap_score: 0,
        components: { demand: 0, supply_scarcity: 0, unmet_need: 0 },
        validity: {
          confidence: 0.2,
          sample_size: 13,
          platforms: ["hardcover"],
          oldest_signal: null,
          newest_signal: null,
          incomplete: true,
          blind_spot: false,
          recent_supply_surge: false,
        },
        top_complaints: [],
        demand_evidence: {},
        ...overrides,
      },
    ],
  };
}

// Fixture (a): the realistic, most important case — proven at the W4 gate
// ("Atomic Habits": 50 reviews, 0 clusters). Clusters empty, fresh-only.
function emptyClustersCounts(): LiveSearchCounts {
  return {
    title: "Atomic Habits",
    review_count: 50,
    fresh_only: true,
    agreement_pct: 0,
    clusters: [],
    pack: pack(),
  };
}

// Fixture (b): enough fresh + historical volume that clusters actually
// formed, merged cross-platform.
function withClustersCounts(): LiveSearchCounts {
  return {
    title: "Deep Work",
    review_count: 240,
    fresh_only: false,
    agreement_pct: 0.62,
    clusters: [
      {
        label: "pacing drags in the middle chapters",
        representative: "pacing drags in the middle chapters",
        reviewer_count: 18,
        platforms: ["hardcover", "amazon_corpus"],
        cross_platform: true,
      },
      {
        label: "examples feel dated",
        representative: "examples feel dated",
        reviewer_count: 7,
        platforms: ["hardcover"],
        cross_platform: false,
      },
    ],
    pack: pack({
      validity: {
        confidence: 0.7,
        sample_size: 60,
        platforms: ["hardcover", "amazon_corpus"],
        oldest_signal: "2022-01-01",
        newest_signal: "2026-06-01",
        incomplete: false,
        blind_spot: false,
        recent_supply_surge: false,
      },
    }),
  };
}

describe("SearchResult", () => {
  it("(a) clusters empty: renders rating/review-count/provenance + fresh_only and low_signal framing — NOT as a failure or empty state", () => {
    render(<SearchResult counts={emptyClustersCounts()} />);

    // Resolved title + sample size are present.
    expect(screen.getByText("Atomic Habits")).toBeInTheDocument();
    expect(screen.getByText(/50 reviews pulled live from Hardcover/)).toBeInTheDocument();
    expect(screen.getByText(/13 critical/)).toBeInTheDocument();

    // Provenance: platform + fresh-only framing.
    expect(screen.getByText("hardcover")).toBeInTheDocument();
    expect(
      screen.getByText("No historical depth — live Hardcover only."),
    ).toBeInTheDocument();
    expect(screen.getByText("Fresh only")).toBeInTheDocument();

    // Honest low-signal note replaces the cluster section — not a blank
    // panel, not a "no results" dead end, and not styled as a failure.
    expect(
      screen.getByText(/low signal: 50 reviews, no distinct complaint clusters/),
    ).toBeInTheDocument();
    expect(screen.getByText("Low signal")).toBeInTheDocument();
    expect(screen.queryByText("Couldn't resolve that title")).not.toBeInTheDocument();
    expect(screen.queryByText(/no results/i)).not.toBeInTheDocument();

    // The download action is still offered — a complete result, not a dead end.
    expect(
      screen.getByRole("button", { name: /download context pack/i }),
    ).toBeInTheDocument();
  });

  it("(b) clusters present: renders the bonus cluster section below the summary", () => {
    render(<SearchResult counts={withClustersCounts()} />);

    expect(screen.getByText("Deep Work")).toBeInTheDocument();
    expect(
      screen.getByText("Historical seeded corpus + live Hardcover, merged."),
    ).toBeInTheDocument();

    expect(screen.getByText("Complaint clusters")).toBeInTheDocument();
    expect(screen.getByText("pacing drags in the middle chapters")).toBeInTheDocument();
    expect(screen.getByText("18 reviewers")).toBeInTheDocument();
    expect(screen.getByText("examples feel dated")).toBeInTheDocument();
    expect(screen.getByText("cross-platform")).toBeInTheDocument();

    // No low-signal note when clusters exist.
    expect(screen.queryByText("Low signal")).not.toBeInTheDocument();

    // Summary section (title) still renders above the cluster section.
    const title = screen.getByText("Deep Work");
    const clusterHeading = screen.getByText("Complaint clusters");
    expect(
      title.compareDocumentPosition(clusterHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("shows an honest not-found state instead of crashing when Hardcover can't resolve the title", () => {
    const counts: LiveSearchCounts = {
      title: "some unresolvable title",
      review_count: 0,
      fresh_only: true,
      agreement_pct: 0,
      clusters: [],
      not_found: true,
      pack: pack(),
    };

    render(<SearchResult counts={counts} />);

    expect(screen.getByText("Couldn't resolve that title")).toBeInTheDocument();
  });
});
