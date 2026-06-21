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
    rating_avg: 4.2,
    rating_count: 13,
    rating_distribution: { "1": 1, "2": 1, "3": 2, "4": 4, "5": 5 },
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
    rating_avg: 4.5,
    rating_count: 60,
    rating_distribution: { "1": 2, "2": 3, "3": 5, "4": 20, "5": 30 },
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

    // Rating summary leads the result, above the title/provenance section.
    const ratingFigure = screen.getByText("4.2");
    expect(ratingFigure).toBeInTheDocument();
    expect(screen.getByText(/from 13 rated reviews/)).toBeInTheDocument();

    // Resolved title + sample size are present.
    expect(screen.getByText("Atomic Habits")).toBeInTheDocument();
    expect(screen.getByText(/50 reviews pulled live from Hardcover/)).toBeInTheDocument();
    expect(screen.getByText(/13 critical/)).toBeInTheDocument();

    // Rating summary renders ABOVE (precedes in document order) the title.
    const title = screen.getByText("Atomic Habits");
    expect(
      ratingFigure.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

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

    expect(screen.getByText("4.5")).toBeInTheDocument();
    expect(screen.getByText(/from 60 rated reviews/)).toBeInTheDocument();

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
      rating_avg: null,
      rating_count: 0,
      rating_distribution: { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 },
      not_found: true,
      pack: pack(),
    };

    render(<SearchResult counts={counts} />);

    expect(screen.getByText("Couldn't resolve that title")).toBeInTheDocument();
  });

  it("shows an honest 'no ratings available' line instead of a fabricated 0 when rating_avg is null", () => {
    const counts: LiveSearchCounts = {
      ...emptyClustersCounts(),
      rating_avg: null,
      rating_count: 0,
      rating_distribution: { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 },
    };

    render(<SearchResult counts={counts} />);

    expect(screen.getByText("No ratings available.")).toBeInTheDocument();
    expect(screen.queryByText("0 / 5")).not.toBeInTheDocument();
    expect(screen.queryByText(/from 0 rated review/)).not.toBeInTheDocument();
  });
});
