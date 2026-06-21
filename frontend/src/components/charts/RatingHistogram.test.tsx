import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RatingHistogram } from "./RatingHistogram";

describe("RatingHistogram", () => {
  it("renders the rating distribution with provenance", () => {
    render(
      <RatingHistogram
        distribution={{ "1": 1, "2": 1, "3": 2, "4": 4, "5": 5 }}
        total={13}
      />,
    );

    expect(screen.getByText("Rating distribution")).toBeInTheDocument();
    expect(screen.getByText("n=13")).toBeInTheDocument();
    // Axis ticks for each star band render as text in the SVG.
    expect(screen.getByText("1★")).toBeInTheDocument();
    expect(screen.getByText("5★")).toBeInTheDocument();
  });

  it("renders an honest empty state instead of a blank box when there are no ratings", () => {
    render(
      <RatingHistogram
        distribution={{ "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 }}
        total={0}
      />,
    );

    expect(screen.getByText("No ratings available")).toBeInTheDocument();
    expect(
      screen.getByText(/isn't a zero rating, it's an absence of one/),
    ).toBeInTheDocument();
    expect(screen.queryByText("1★")).not.toBeInTheDocument();
  });
});
