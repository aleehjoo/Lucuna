"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { FlagBadge } from "@/components/ui/FlagBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import { JobStatus } from "@/components/JobStatus";
import { useCandidates, useStartSweep } from "@/lib/hooks";
import type { CandidateOut, JobOut } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// Category Sweep — the operator's BISAC-wide gap-ranking surface (Frontend
// PRD §6.5 / Plan B Task 10). Unlike Search (live, single-title, user-facing)
// and the Niche Dashboard (browse), this surface RUNS a corpus-only scoring
// pass on demand (~25s background job) and ranks every BISAC-scope candidate
// by gap_score. It is explicitly an advanced/operator view — surfaced with a
// quiet banner, not hidden, but not styled as the product's front door.
//
// NO charts here: the gold-leaf Gap-Strip and other Recharts visualizations
// are W7 (per the task brief). Rankings render as an expandable list with
// mono figures — same honesty rule as SearchResult/Dashboard: a candidate's
// confidence/incomplete/blind_spot flags are always visible, never smoothed
// over to make a thin result look stronger than it is.
export default function CategorySweepPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const candidates = useCandidates(projectId);
  const startSweep = useStartSweep(projectId);

  const [jobId, setJobId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportingFormat, setExportingFormat] = useState<"json" | "md" | null>(null);

  async function handleRunSweep() {
    setStartError(null);
    try {
      const { job_id } = await startSweep.mutateAsync();
      setJobId(job_id);
    } catch (err) {
      setStartError(
        err instanceof Error ? err.message : "Couldn't start the sweep.",
      );
    }
  }

  function handleDone(_job: JobOut) {
    // useStartSweep already invalidates ["candidates", projectId] onSettled,
    // but an explicit refetch here keeps this surface self-contained even if
    // that wiring ever changes.
    candidates.refetch();
  }

  function handleRetryJob() {
    setJobId(null);
  }

  async function handleExport(format: "json" | "md") {
    setExportError(null);
    setExportingFormat(format);
    try {
      const res = await fetch(
        `${API_BASE}/projects/${projectId}/export?scope=category_sweep&format=${format}`,
      );
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const body = format === "md" ? await res.text() : JSON.stringify(await res.json(), null, 2);
      const blob = new Blob([body], {
        type: format === "md" ? "text/markdown" : "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `category-sweep-${projectId}.${format === "md" ? "md" : "json"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(
        err instanceof Error ? err.message : "Couldn't export the Context Pack.",
      );
    } finally {
      setExportingFormat(null);
    }
  }

  const candidateList = candidates.data ?? [];
  const sweepRunning = !!jobId;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8 py-6">
      <div className="flex flex-col gap-1">
        <h1 className="display text-3xl text-[var(--ink)]">Category Sweep</h1>
        <p className="text-sm text-[var(--muted)]">
          Rank BISAC-wide gap candidates across this niche&apos;s seeded corpus.
        </p>
      </div>

      {/* 1. Advanced-mode banner (§6.5) — quiet, not alarming. */}
      <div
        role="note"
        className="rounded-md border border-[var(--border)] bg-[color-mix(in_srgb,var(--ink)_4%,transparent)] px-4 py-3 text-sm text-[var(--muted)]"
      >
        Advanced view: Category Sweep re-scores the whole seeded corpus at
        once. Most workflows only need Search or the Niche Dashboard &mdash;
        come here when you want a ranked, exportable list of gap candidates
        across the entire category.
      </div>

      {/* 2. Run Sweep action + job progress. */}
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 className="display text-lg text-[var(--ink)]">Run sweep</h2>
            <p className="text-sm text-[var(--muted)]">
              Re-scores every BISAC-scope candidate from the seeded corpus.
              Takes about 25 seconds.
            </p>
          </div>
          <Button
            variant="primary"
            onClick={handleRunSweep}
            disabled={startSweep.isPending || sweepRunning}
          >
            {startSweep.isPending ? "Starting…" : "Run Sweep"}
          </Button>
        </div>
        {startError ? (
          <p className="text-sm text-[var(--oxblood)]">{startError}</p>
        ) : null}
        {jobId ? (
          <JobStatus
            jobId={jobId}
            variant="bar"
            onDone={handleDone}
            onRetry={handleRetryJob}
          />
        ) : null}
      </Card>

      {/* 3. Ranked BISAC candidates. */}
      {candidates.isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : candidates.isError ? (
        <ErrorState
          message="Couldn't load gap candidates."
          onRetry={() => candidates.refetch()}
        />
      ) : candidateList.length === 0 ? (
        <EmptyState
          title="No gap candidates yet"
          description="Run a sweep to score this category's BISAC-wide gap candidates."
        />
      ) : (
        <Card className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="display text-lg text-[var(--ink)]">
              Ranked candidates
            </h2>
            <span className="data text-xs text-[var(--muted)]">
              {candidateList.length} candidate{candidateList.length === 1 ? "" : "s"}
            </span>
          </div>
          <ol className="flex flex-col gap-3">
            {candidateList
              .slice()
              .sort((a, b) => b.gap_score - a.gap_score)
              .map((c, i) => (
                <CandidateRow key={`${c.scope}-${c.ref_id}`} candidate={c} rank={i + 1} />
              ))}
          </ol>
        </Card>
      )}

      {/* 4. Context Pack export. */}
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="display text-lg text-[var(--ink)]">
            Export Context Pack
          </h2>
          <p className="text-sm text-[var(--muted)]">
            Regenerates the category-sweep Context Pack from the current
            seeded corpus.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            onClick={() => handleExport("json")}
            disabled={exportingFormat !== null}
          >
            {exportingFormat === "json" ? "Exporting…" : "Download JSON"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => handleExport("md")}
            disabled={exportingFormat !== null}
          >
            {exportingFormat === "md" ? "Exporting…" : "Download Markdown"}
          </Button>
        </div>
        {exportError ? (
          <p className="w-full text-sm text-[var(--oxblood)]">{exportError}</p>
        ) : null}
      </Card>
    </div>
  );
}

// A single ranked candidate row, expandable to reveal validity flags,
// provenance (platforms), and the demand/supply/unmet_need components that
// fed gap_score. Collapsed by default so the ranked list stays scannable;
// the honesty signals (confidence, incomplete, blind_spot) are visible even
// collapsed so a thin candidate is never mistaken for a strong one.
function CandidateRow({ candidate, rank }: { candidate: CandidateOut; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const confidencePct = Math.round(candidate.confidence * 100);
  const lowConfidence = candidate.confidence < 0.5;

  return (
    <li className="flex flex-col gap-2 border-b border-[var(--border)] pb-3 last:border-b-0 last:pb-0">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full flex-wrap items-center justify-between gap-3 text-left"
      >
        <div className="flex items-center gap-3">
          <span className="data text-xs text-[var(--muted)]">#{rank}</span>
          <span className="text-sm font-medium text-[var(--ink)]">
            {candidate.title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="data text-sm text-[var(--ink)]">
            {candidate.gap_score.toFixed(2)}
          </span>
          <span
            className={`data text-xs ${
              lowConfidence ? "text-[var(--oxblood)]" : "text-[var(--muted)]"
            }`}
          >
            {confidencePct}% conf.
          </span>
          <span className="data text-xs text-[var(--muted)]">
            n={candidate.sample_size}
          </span>
          {candidate.incomplete ? <FlagBadge flag="incomplete" /> : null}
          {candidate.blind_spot ? <FlagBadge flag="blind_spot" /> : null}
          {candidate.recent_supply_surge ? (
            <FlagBadge flag="recent_supply_surge" />
          ) : null}
          <span aria-hidden="true" className="text-[var(--muted)]">
            {expanded ? "−" : "+"}
          </span>
        </div>
      </button>

      {expanded ? (
        <div className="flex flex-col gap-3 rounded-md bg-[color-mix(in_srgb,var(--ink)_4%,transparent)] px-3 py-3">
          {lowConfidence ? (
            <p className="text-sm text-[var(--oxblood)]">
              Low confidence ({confidencePct}%) on a sample of{" "}
              {candidate.sample_size} &mdash; treat this ranking as
              directional, not a confident signal.
            </p>
          ) : null}
          <div className="grid grid-cols-3 gap-3">
            <Figure label="Demand" value={candidate.demand_score} />
            <Figure label="Supply scarcity" value={candidate.supply_scarcity} />
            <Figure label="Unmet need" value={candidate.unmet_need} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {candidate.platforms_used.length === 0 ? (
              <span className="text-xs text-[var(--muted)]">
                No platform provenance recorded.
              </span>
            ) : (
              candidate.platforms_used.map((p) => (
                <Chip key={p} mono>
                  {p}
                </Chip>
              ))
            )}
          </div>
        </div>
      ) : null}
    </li>
  );
}

function Figure({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="data text-sm text-[var(--ink)]">{value.toFixed(2)}</span>
      <span className="text-xs text-[var(--muted)]">{label}</span>
    </div>
  );
}
