"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { FlagBadge } from "@/components/ui/FlagBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import { useWork } from "@/lib/hooks";
import type { ClusterOut } from "@/lib/types";

// Work Detail — the landing page for a work row clicked from the Niche
// Dashboard (`/p/{projectId}/works/{workId}`). Mirrors the same honesty
// rules as Dashboard/SearchResult: a work with 0 or degenerate complaint
// clusters still renders a complete page (rating + provenance), never a
// blank panel; a work that isn't in this project (backend 404) renders an
// EmptyState with a path back, never a raw error. NO charts here — the
// rating distribution chart etc. is W7; figures stay mono text for now.
export default function WorkDetailPage() {
  const params = useParams<{ projectId: string; workId: string }>();
  const { projectId, workId } = params;

  const work = useWork(projectId, workId);

  const backLink = (
    <Link
      href={`/p/${projectId}/dashboard`}
      className="text-sm text-[var(--muted)] transition hover:text-[var(--ultramarine)]"
    >
      &larr; Back to Niche Dashboard
    </Link>
  );

  if (work.isLoading) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-8 py-6">
        {backLink}
        <Skeleton className="h-9 w-80" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (work.isError) {
    const notFound = work.error instanceof ApiError && work.error.status === 404;

    if (notFound) {
      return (
        <div className="mx-auto flex max-w-3xl flex-col gap-8 py-6">
          {backLink}
          <EmptyState
            title="That title isn't in this project"
            description="This work either doesn't exist or belongs to a different project."
            action={
              <Link
                href={`/p/${projectId}/dashboard`}
                className="inline-flex items-center gap-2 rounded-md bg-[var(--ultramarine)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
              >
                Back to Niche Dashboard
              </Link>
            }
          />
        </div>
      );
    }

    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-8 py-6">
        {backLink}
        <ErrorState
          message="Couldn't load this work."
          onRetry={() => work.refetch()}
        />
      </div>
    );
  }

  const data = work.data;
  if (!data) {
    // Defensive — react-query only reaches here once loading/error are both
    // false, which implies data is set, but keep this honest rather than
    // rendering a half-built page off an undefined value.
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-8 py-6">
        {backLink}
        <ErrorState message="Couldn't load this work." onRetry={() => work.refetch()} />
      </div>
    );
  }

  const clusters = data.clusters ?? [];
  const distinctLabels = new Set(clusters.map((c) => c.label)).size;
  const lowSignal = clusters.length === 0 || clusters.length <= 1 || distinctLabels <= 1;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 py-6">
      {backLink}

      {/* Header: title, author, rating summary — mono numerals, honest
          "No rating" when agg_rating_avg is null (never a fabricated 0). */}
      <div className="flex flex-col gap-2">
        <h1 className="display text-3xl text-[var(--ink)]">{data.title}</h1>
        <p className="text-sm text-[var(--muted)]">{data.author ?? "Unknown author"}</p>
      </div>

      <Card className="flex flex-col gap-3">
        {data.agg_rating_avg !== null ? (
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="data text-4xl text-[var(--ink)]">
              {data.agg_rating_avg.toFixed(1)}
              <span className="text-lg text-[var(--muted)]"> / 5</span>
            </span>
            <span className="data text-sm text-[var(--muted)]">
              from {data.agg_rating_count ?? 0} rated review
              {(data.agg_rating_count ?? 0) === 1 ? "" : "s"}
            </span>
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">No rating</p>
        )}
        <p className="data text-sm text-[var(--muted)]">
          {data.review_count} review{data.review_count === 1 ? "" : "s"} total
        </p>
      </Card>

      {/* Complaint clusters — same thin-data honesty as Dashboard/Search:
          0 clusters, a single cluster, or every cluster sharing one label is
          a low-signal result. Still shows the rating/provenance above; never
          a blank panel. */}
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="display text-lg text-[var(--ink)]">Complaint clusters</h2>
          {lowSignal ? <FlagBadge flag="low_signal" /> : null}
        </div>
        {lowSignal ? (
          <p className="text-sm text-[var(--muted)]">
            low signal: {data.review_count} review{data.review_count === 1 ? "" : "s"}, no
            distinct complaint clusters &mdash; interpret cautiously
          </p>
        ) : null}
        {clusters.length > 0 ? (
          <ul className="flex flex-col gap-3">
            {clusters.map((cluster) => (
              <ClusterRow key={cluster.id} cluster={cluster} />
            ))}
          </ul>
        ) : null}
      </Card>
    </div>
  );
}

function ClusterRow({ cluster }: { cluster: ClusterOut }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] pb-3 last:border-b-0 last:pb-0">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-medium text-[var(--ink)]">{cluster.label}</span>
        <span className="text-xs text-[var(--muted)]">{cluster.representative}</span>
        <span className="data text-xs text-[var(--muted)]">
          {cluster.reviewer_count} reviewer{cluster.reviewer_count === 1 ? "" : "s"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        {cluster.platforms.map((p) => (
          <Chip key={p} mono>
            {p}
          </Chip>
        ))}
        {cluster.cross_platform ? (
          <Chip className="border-[var(--ultramarine)] text-[var(--ultramarine)]">
            cross-platform
          </Chip>
        ) : null}
      </div>
    </li>
  );
}
