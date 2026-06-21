"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { JobStatus } from "@/components/JobStatus";
import { useProjectJobs, useStartSeed } from "@/lib/hooks";
import type { JobOut, SeedRequestBody } from "@/lib/types";

const DEFAULTS: SeedRequestBody = {
  meta_limit: 200_000,
  review_limit: 1_000_000,
  max_works: 25,
};

const FIELDS: Array<{
  key: keyof SeedRequestBody;
  label: string;
  hint: string;
}> = [
  {
    key: "meta_limit",
    label: "Meta limit",
    hint: "Max book/work metadata records to scan.",
  },
  {
    key: "review_limit",
    label: "Review limit",
    hint: "Max review records to scan and match.",
  },
  {
    key: "max_works",
    label: "Max works",
    hint: "Max distinct works to seed into this niche.",
  },
];

// Seed & Data — the operator surface for kicking off the batch seed (Frontend
// PRD §6.2 item 6 / §6.6 / §8 / Plan B Task 11). This is the one surface in
// the product whose primary action takes ~1 HOUR: the backend spawns the
// existing `lacuna seed` CLI as a background subprocess and streams progress
// into the `jobs` table (PRD §8: "The user can navigate away and come back;
// the job keeps running"). That means this page's job-tracking state must be
// resumable from the job id alone — never from component state that dies on
// unmount — so a running seed survives a refresh or a trip to another tab.
export default function SeedPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const startSeed = useStartSeed(projectId);
  const jobs = useProjectJobs(projectId);

  const [metaLimit, setMetaLimit] = useState(DEFAULTS.meta_limit);
  const [reviewLimit, setReviewLimit] = useState(DEFAULTS.review_limit);
  const [maxWorks, setMaxWorks] = useState(DEFAULTS.max_works);
  const [jobId, setJobId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  // Tracks whether the active jobId came from auto-resuming an in-flight job
  // found on mount (vs. a job this session just started) — purely cosmetic
  // copy, doesn't change the polling mechanics.
  const [resumed, setResumed] = useState(false);

  const seedJobs = useMemo(
    () => (jobs.data ?? []).filter((j) => j.kind === "seed"),
    [jobs.data],
  );

  // Auto-resume: if there's already a running/queued seed job for this
  // project when the page mounts (e.g. the operator started it, navigated
  // away, and came back), pick it up automatically instead of showing a
  // blank trigger form in front of a job that's actually still going.
  useEffect(() => {
    if (jobId) return; // already tracking one this session
    const inFlight = seedJobs.find(
      (j) => j.status === "running" || j.status === "queued",
    );
    if (inFlight) {
      setJobId(inFlight.id);
      setResumed(true);
    }
    // Only run this scan once jobs have loaded for the first time.
  }, [seedJobs, jobId]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStartError(null);
    try {
      const { job_id } = await startSeed.mutateAsync({
        meta_limit: metaLimit,
        review_limit: reviewLimit,
        max_works: maxWorks,
      });
      setResumed(false);
      setJobId(job_id);
    } catch (err) {
      setStartError(
        err instanceof Error ? err.message : "Couldn't start the seed.",
      );
    }
  }

  function handleDone(_job: JobOut) {
    jobs.refetch();
  }

  function handleRetryJob() {
    setJobId(null);
    setResumed(false);
  }

  const seeding = !!jobId;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 py-6">
      <div className="flex flex-col gap-1">
        <h1 className="display text-3xl text-[var(--ink)]">Seed & Data</h1>
        <p className="text-sm text-[var(--muted)]">
          Operator surface: pull historical metadata and reviews into this
          niche&apos;s corpus.
        </p>
      </div>

      {/* Honest long-operation framing — PRD §8: the seed is a background
          subprocess; it survives navigation, refresh, even closing the tab. */}
      <div
        role="note"
        className="rounded-md border border-[var(--border)] bg-[color-mix(in_srgb,var(--ink)_4%,transparent)] px-4 py-3 text-sm text-[var(--muted)]"
      >
        <strong className="font-medium text-[var(--ink)]">
          This is a long operation &mdash; about 1 hour.
        </strong>{" "}
        The seed runs as a background subprocess, not a request this tab has
        to hold open. You can navigate away, close this tab, or come back
        later &mdash; the job keeps running on the server, and its progress
        will be exactly where you left it when you return to this page.
      </div>

      {/* 1. Trigger form. */}
      <Card className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="display text-lg text-[var(--ink)]">Start a seed</h2>
          <p className="text-sm text-[var(--muted)]">
            Scans metadata and reviews up to the limits below, then matches,
            clusters, and scores what it finds.
          </p>
        </div>

        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {FIELDS.map((field) => (
              <div key={field.key} className="flex flex-col gap-1">
                <label
                  htmlFor={`seed-${field.key}`}
                  className="text-sm font-medium text-[var(--ink)]"
                >
                  {field.label}
                </label>
                <input
                  id={`seed-${field.key}`}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  step={1}
                  value={
                    field.key === "meta_limit"
                      ? metaLimit
                      : field.key === "review_limit"
                        ? reviewLimit
                        : maxWorks
                  }
                  onChange={(e) => {
                    const value = Math.max(0, Number(e.target.value) || 0);
                    if (field.key === "meta_limit") setMetaLimit(value);
                    else if (field.key === "review_limit") setReviewLimit(value);
                    else setMaxWorks(value);
                  }}
                  disabled={seeding || startSeed.isPending}
                  className="data rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus-visible:border-[var(--ultramarine)] disabled:opacity-50"
                />
                <span className="text-xs text-[var(--muted)]">{field.hint}</span>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Button
              type="submit"
              variant="primary"
              disabled={startSeed.isPending || seeding}
            >
              {startSeed.isPending ? "Starting…" : "Start seed"}
            </Button>
            {seeding ? (
              <span className="text-sm text-[var(--muted)]">
                A seed is already running for this project.
              </span>
            ) : null}
          </div>
        </form>

        {startError ? (
          <p className="text-sm text-[var(--oxblood)]">{startError}</p>
        ) : null}

        {/* 2. Live progress — job-id-driven, so it survives navigation. */}
        {jobId ? (
          <div className="flex flex-col gap-2 border-t border-[var(--border)] pt-4">
            {resumed ? (
              <p className="text-xs text-[var(--muted)]">
                Resumed an in-progress seed found for this project.
              </p>
            ) : null}
            <JobStatus
              jobId={jobId}
              variant="bar"
              onDone={handleDone}
              onRetry={handleRetryJob}
            />
          </div>
        ) : null}
      </Card>

      {/* 3. Past seed jobs. */}
      <Card className="flex flex-col gap-4">
        <h2 className="display text-lg text-[var(--ink)]">Past seed jobs</h2>
        {jobs.isLoading ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : jobs.isError ? (
          <ErrorState
            message="Couldn't load past seed jobs."
            onRetry={() => jobs.refetch()}
          />
        ) : seedJobs.length === 0 ? (
          <EmptyState
            title="No seed jobs yet"
            description="Start a seed above to begin building this niche's historical corpus."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {seedJobs.map((job) => (
              <SeedJobRow key={job.id} job={job} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

const STATUS_LABEL: Record<JobOut["status"], string> = {
  queued: "Queued",
  running: "Running",
  done: "Done",
  error: "Error",
};

const STATUS_COLOR: Record<JobOut["status"], string> = {
  queued: "text-[var(--muted)]",
  running: "text-[var(--ultramarine)]",
  done: "text-[var(--muted)]",
  error: "text-[var(--oxblood)]",
};

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown time";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function SeedJobRow({ job }: { job: JobOut }) {
  const counts = job.counts ?? {};
  const countEntries = Object.entries(counts).filter(
    ([, v]) => typeof v === "number" || typeof v === "string",
  );

  return (
    <li className="flex flex-col gap-2 border-b border-[var(--border)] pb-3 last:border-b-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${STATUS_COLOR[job.status]}`}>
            {STATUS_LABEL[job.status]}
          </span>
          {job.status === "running" || job.status === "queued" ? (
            <span className="data text-xs text-[var(--muted)]">
              {Math.round(job.progress_pct ?? 0)}%
              {job.step ? ` · ${job.step}` : ""}
            </span>
          ) : null}
        </div>
        <span className="data text-xs text-[var(--muted)]">
          started {formatTimestamp(job.created_at)}
        </span>
      </div>

      {job.status === "error" && job.error_detail ? (
        <p className="text-sm text-[var(--oxblood)]">{job.error_detail}</p>
      ) : null}

      {job.status === "done" && countEntries.length > 0 ? (
        <div className="flex flex-wrap gap-3">
          {countEntries.map(([k, v]) => (
            <span key={k} className="data text-xs text-[var(--muted)]">
              {k}: <span className="text-[var(--ink)]">{String(v)}</span>
            </span>
          ))}
        </div>
      ) : null}

      <span className="text-xs text-[var(--muted)]">
        updated {formatTimestamp(job.updated_at)}
      </span>
    </li>
  );
}
