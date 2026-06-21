import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProvenanceChips } from "./ProvenanceChips";

describe("ProvenanceChips", () => {
  it("renders sample size and platform chips", () => {
    render(<ProvenanceChips sampleSize={40} platforms={["hardcover", "amazon_corpus"]} />);

    expect(screen.getByText("n=40")).toBeInTheDocument();
    expect(screen.getByText("hardcover")).toBeInTheDocument();
    expect(screen.getByText("amazon_corpus")).toBeInTheDocument();
  });

  it("renders an honest note instead of a blank chip row when there's no platform provenance", () => {
    render(<ProvenanceChips sampleSize={0} platforms={[]} />);

    expect(screen.getByText("n=0")).toBeInTheDocument();
    expect(screen.getByText("No platform provenance recorded.")).toBeInTheDocument();
  });

  it("renders a date-range chip when oldest/newest signal are present", () => {
    render(
      <ProvenanceChips
        sampleSize={60}
        platforms={["hardcover"]}
        oldestSignal="2022-01-01T00:00:00Z"
        newestSignal="2026-06-01T00:00:00Z"
      />,
    );

    expect(screen.getByText(/2022-01-01.*2026-06-01/)).toBeInTheDocument();
  });

  it("dims and labels a stale date-range (newest signal > 18 months old)", () => {
    render(
      <ProvenanceChips
        sampleSize={13}
        platforms={["hardcover"]}
        oldestSignal="2019-01-01T00:00:00Z"
        newestSignal="2020-01-01T00:00:00Z"
      />,
    );

    expect(screen.getByText(/stale/)).toBeInTheDocument();
  });

  it("omits the date-range chip when no date range is available", () => {
    render(<ProvenanceChips sampleSize={5} platforms={["hardcover"]} />);

    expect(screen.queryByText(/stale/)).not.toBeInTheDocument();
  });
});
