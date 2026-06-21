import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { HypothesisBanner } from "./HypothesisBanner";

describe("HypothesisBanner", () => {
  it("renders the hypothesis-not-a-finding posture", () => {
    render(<HypothesisBanner />);

    expect(
      screen.getByText(/treat each candidate as a hypothesis, not a finding/i),
    ).toBeInTheDocument();
  });

  it("is an accessible note, not an alarming alert", () => {
    render(<HypothesisBanner />);

    expect(screen.getByRole("note")).toBeInTheDocument();
  });
});
