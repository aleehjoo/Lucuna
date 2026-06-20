"use client";

import { useEffect, useRef } from "react";
import { useJob } from "@/lib/hooks";
import type { JobOut } from "@/lib/types";
import { Button } from "@/components/ui/Button";

type Variant = "bar" | "inline";

const STEP_FALLBACK: Record<"queued" | "running", string> = {
  queued: "queued…",
  running: "working…",
};

/**
 * Core async UX for every job-backed action (seed, search, sweep). Polls via
 * `useJob` and renders the state the job is actually in — never a blank
 * panel. `variant="bar"` is for long-running jobs (seed): a real progress bar
 * with `progress_pct` + `step`. `variant="inline"` is for fast jobs (search):
 * a lightweight spinner + step, no bar.
 */
export function JobStatus({
  jobId,
  onDone,
  onRetry,
  variant = "bar",
}: {
  jobId: string | null;
  onDone?: (job: JobOut) => void;
  onRetry?: () => void;
  variant?: Variant;
}) {
  const { data: job, isLoading } = useJob(jobId);
  const firedFor = useRef<string | null>(null);

  useEffect(() => {
    if (job?.status === "done" && firedFor.current !== job.id) {
      firedFor.current = job.id;
      onDone?.(job);
    }
  }, [job, onDone]);

  if (!jobId) return null;

  if (isLoading && !job) {
    return (
      <StatusShell variant={variant}>
        <Spinner />
        <span className="text-[var(--muted)]">connecting…</span>
      </StatusShell>
    );
  }

  if (!job) {
    // Polling failed to ever return a job — still actionable, not blank.
    return (
      <StatusShell variant={variant}>
        <span className="text-[var(--oxblood)]">
          Couldn&apos;t load job status.
        </span>
        {onRetry ? (
          <Button variant="ghost" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </StatusShell>
    );
  }

  if (job.status === "error") {
    const cancelled = job.error_detail === "cancelled";
    return (
      <StatusShell variant={variant}>
        <span
          className={cancelled ? "text-[var(--muted)]" : "text-[var(--oxblood)]"}
        >
          {cancelled ? "Cancelled" : job.error_detail || "Something went wrong."}
        </span>
        {!cancelled && onRetry ? (
          <Button variant="ghost" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </StatusShell>
    );
  }

  if (job.status === "done") {
    return (
      <StatusShell variant={variant}>
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--ultramarine)]" />
        <span className="text-[var(--muted)]">Done.</span>
      </StatusShell>
    );
  }

  // queued | running
  const step = job.step || STEP_FALLBACK[job.status];
  const pct = Math.max(0, Math.min(100, Math.round(job.progress_pct ?? 0)));

  if (variant === "inline") {
    return (
      <StatusShell variant={variant}>
        <Spinner />
        <span className="text-[var(--muted)]">{step}</span>
        <span
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={step}
          className="sr-only"
        >
          {pct}%
        </span>
      </StatusShell>
    );
  }

  return (
    <div className="flex flex-col gap-2" data-variant={variant}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-[var(--muted)]">{step}</span>
        <span className="data text-[var(--ink)]">{pct}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={step}
        className="h-1.5 w-full overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--ink)_8%,transparent)]"
      >
        <div
          className="h-full rounded-full bg-[var(--ultramarine)] transition-[width] motion-reduce:transition-none"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function StatusShell({
  variant,
  children,
}: {
  variant: Variant;
  children: React.ReactNode;
}) {
  return (
    <div
      data-variant={variant}
      className="flex items-center gap-2 text-sm"
    >
      {children}
    </div>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="h-3 w-3 animate-spin rounded-full border-2 border-[color-mix(in_srgb,var(--ink)_15%,transparent)] border-t-[var(--ultramarine)] motion-reduce:animate-none"
    />
  );
}
