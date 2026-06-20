import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { FlagBadge } from "./FlagBadge";

describe("FlagBadge", () => {
  it("renders the fresh_only label with its live-data-only tooltip", () => {
    render(<FlagBadge flag="fresh_only" />);
    const badge = screen.getByText("Fresh only");
    expect(badge).toBeInTheDocument();
    expect(badge.getAttribute("title")).toContain("No historical depth");
  });

  it("renders the low_signal label with its cautious-interpretation tooltip", () => {
    render(<FlagBadge flag="low_signal" />);
    const badge = screen.getByText("Low signal");
    expect(badge).toBeInTheDocument();
    expect(badge.getAttribute("title")).toContain("interpret cautiously");
  });
});
