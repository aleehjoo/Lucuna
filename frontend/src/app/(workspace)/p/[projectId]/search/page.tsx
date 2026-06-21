"use client";

import { FormEvent, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { JobStatus } from "@/components/JobStatus";
import { SearchResult } from "@/components/SearchResult";
import { useStartSearch } from "@/lib/hooks";
import type { JobOut, LiveSearchCounts } from "@/lib/types";

// Backend maps a missing HARDCOVER_API_TOKEN to a 503 on POST /search
// (api/routers/search.py) — that's a configuration fact about this instance,
// not a failure of the search itself, so it gets its own quiet notice
// (Frontend PRD §11 graceful degradation) rather than the oxblood "something
// broke" treatment `submitError` otherwise renders.
const HARDCOVER_UNAVAILABLE_MESSAGE =
  "Live search isn't available — the Hardcover key isn't configured on this instance.";

// Live single-title search — the most important surface in the product.
// Resolves ONE title against Hardcover, live, in seconds (never the seeded
// corpus — Frontend PRD §3.2 / CLAUDE.md §3). Small fresh batches routinely
// yield zero complaint clusters (proven at the W4 gate on "Atomic Habits":
// 50 reviews, 0 clusters); SearchResult is built so that's still a complete,
// honest result, never a dead end.
export default function SearchPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const startSearch = useStartSearch(projectId);

  const [query, setQuery] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<LiveSearchCounts | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [hardcoverUnavailable, setHardcoverUnavailable] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitError(null);
    setHardcoverUnavailable(false);
    setResult(null);

    const trimmed = query.trim();
    if (!trimmed) {
      setSubmitError("Enter a book title or ISBN to search.");
      return;
    }

    // ISBN-10/13 (digits, optionally with hyphens, optional trailing X) vs a
    // free-text title — the backend's SearchRequest takes one or the other.
    const isIsbn = /^[0-9][0-9-]{8,16}[0-9xX]$/.test(trimmed.replace(/\s/g, ""));

    try {
      const { job_id } = await startSearch.mutateAsync(
        isIsbn ? { isbn: trimmed } : { title: trimmed },
      );
      setJobId(job_id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setHardcoverUnavailable(true);
        return;
      }
      setSubmitError(
        err instanceof Error ? err.message : "Couldn't start the search.",
      );
    }
  }

  function handleDone(job: JobOut) {
    if (job.counts) {
      setResult(job.counts as unknown as LiveSearchCounts);
    }
  }

  function handleRetry() {
    setJobId(null);
    setResult(null);
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 py-6">
      <div className="flex flex-col gap-1">
        <h1 className="display text-3xl text-[var(--ink)]">Search</h1>
        <p className="text-sm text-[var(--muted)]">
          Pull a single title live from Hardcover &mdash; rating, review
          volume, and provenance always come back, with complaint clusters as
          a bonus when there&apos;s enough fresh volume to find them.
        </p>
      </div>

      <Card>
        <form className="flex flex-col gap-3 sm:flex-row" onSubmit={handleSubmit}>
          <label htmlFor="search-query" className="sr-only">
            Search a book title or ISBN
          </label>
          <input
            id="search-query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a book title or ISBN"
            className="flex-1 rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus-visible:border-[var(--ultramarine)]"
          />
          <Button type="submit" variant="primary" disabled={startSearch.isPending}>
            {startSearch.isPending ? "Starting…" : "Search"}
          </Button>
        </form>
        {submitError ? (
          <p className="mt-3 text-sm text-[var(--oxblood)]">{submitError}</p>
        ) : null}
        {hardcoverUnavailable ? (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md border border-[var(--border)] bg-[color-mix(in_srgb,var(--ink)_4%,transparent)] px-3 py-2">
            <p className="text-sm text-[var(--muted)]">
              {HARDCOVER_UNAVAILABLE_MESSAGE}
            </p>
            <Button
              variant="ghost"
              onClick={() => setHardcoverUnavailable(false)}
            >
              Dismiss
            </Button>
          </div>
        ) : null}
      </Card>

      {jobId ? (
        <Card>
          <JobStatus
            jobId={jobId}
            variant="inline"
            onDone={handleDone}
            onRetry={handleRetry}
            cancellable
          />
        </Card>
      ) : null}

      {result ? <SearchResult counts={result} /> : null}
    </div>
  );
}
