import { describe, expect, it } from "vitest";
import { jobRefetchInterval } from "./hooks";
import type { JobOut } from "./types";

function mockQuery(data: Partial<JobOut> | undefined) {
  return { state: { data } } as Parameters<typeof jobRefetchInterval>[0];
}

describe("jobRefetchInterval", () => {
  it("stops polling when the job is done", () => {
    expect(jobRefetchInterval(mockQuery({ status: "done" } as JobOut))).toBe(false);
  });

  it("stops polling when the job errored", () => {
    expect(jobRefetchInterval(mockQuery({ status: "error" } as JobOut))).toBe(false);
  });

  it("keeps polling at 1500ms while the job is running", () => {
    expect(jobRefetchInterval(mockQuery({ status: "running" } as JobOut))).toBe(1500);
  });

  it("keeps polling at 1500ms while the job is queued", () => {
    expect(jobRefetchInterval(mockQuery({ status: "queued" } as JobOut))).toBe(1500);
  });

  it("keeps polling at 1500ms before any data has loaded yet", () => {
    expect(jobRefetchInterval(mockQuery(undefined))).toBe(1500);
  });
});
