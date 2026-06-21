import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AgreementGauge } from "./AgreementGauge";

describe("AgreementGauge", () => {
  it("renders the agreement percentage and sample size", () => {
    render(<AgreementGauge agreementPct={0.62} sampleSize={60} />);

    expect(screen.getByText("Cross-platform agreement")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("n=60")).toBeInTheDocument();
  });

  it("renders a real 0% agreement (a measured disagreement) rather than treating it as missing", () => {
    render(<AgreementGauge agreementPct={0} sampleSize={13} />);

    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("n=13")).toBeInTheDocument();
    expect(screen.queryByText("No agreement signal yet")).not.toBeInTheDocument();
  });

  it("renders an honest empty state instead of a blank box when there's no sample at all", () => {
    render(<AgreementGauge agreementPct={0} sampleSize={0} />);

    expect(screen.getByText("No agreement signal yet")).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
  });
});
