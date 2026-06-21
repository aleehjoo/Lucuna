"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { FlagBadge } from "@/components/ui/FlagBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCandidates, useClusters, useProject, useWorks } from "@/lib/hooks";
import type { CandidateOut, ClusterOut, WorkOut } from "@/lib/types";

// Niche Dashboard — the operator's browse surface for an already-seeded
// project (Frontend PRD §6.4 / Plan B Task 9). Pulls four independent reads
// (project, works, niche-level clusters, candidates) and renders them as
// plain lists/tables — NO charts here; the gold-leaf Gap-Strip and other
// Recharts visualizations are W7 (per the task brief).
//
// Two states this page must never produce: a dead end (an unseeded project
// renders an EmptyState with a path forward, not a blank dashboard) and a
// false impression of confidence (sparse/degenerate niche clusters render
// with an honest low_signal note, mirroring SearchResult's "never present a
// thin result as a confident one" rule).
export default function DashboardPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const project = useProject(projectId);
  const works = useWorks(projectId);
  const clusters = useClusters(projectId, "bisac");
  const candidates = useCandidates(projectId);

  const isLoading =
    project.isLoading || works.isLoading || clusters.isLoading || candidates.isLoading;
  const isError =
    project.isError || works.isError || clusters.isError || candidates.isError;

  function retryAll() {
    project.refetch();
    works.refetch();
    clusters.refetch();
    candidates.refetch();
  }

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-8 py-6">
        <Skeleton className="h-9 w-64" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-8 py-6">
        <ErrorState
          message="Couldn't load this project's dashboard."
          onRetry={retryAll}
        />
      </div>
    );
  }

  const projectData = project.data;
  const workList = works.data ?? [];
  const notSeeded = projectData ? projectData.seeded === false || workList.length === 0 : true;

  if (notSeeded) {
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-8 py-6">
        <div className="flex flex-col gap-1">
          <h1 className="display text-3xl text-[var(--ink)]">
            {projectData?.name ?? "Niche Dashboard"}
          </h1>
        </div>
        <EmptyState
          title="No historical depth yet"
          description="Seed this niche to unlock historical depth — or search any title live."
          action={
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link
                href={`/p/${projectId}/seed`}
                className="inline-flex items-center gap-2 rounded-md bg-[var(--ultramarine)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
              >
                Seed & Data
              </Link>
              <Link
                href={`/p/${projectId}/search`}
                className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--ink)] transition hover:bg-[color-mix(in_srgb,var(--ink)_5%,transparent)]"
              >
                Search a title live
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  const clusterList = clusters.data ?? [];
  // GET /candidates returns BOTH work- and bisac-scope rows; the Dashboard's
  // "Gap candidates" card is per-work (the BISAC-wide view lives on Category
  // Sweep), so only work-scope candidates belong here.
  const candidateList = (candidates.data ?? []).filter((c) => c.scope === "work");
  const totalReviews = workList.reduce((sum, w) => sum + (w.review_count ?? 0), 0);

  // Honesty gate mirroring SearchResult: a handful of clusters, or every
  // cluster sharing one label, is a thin/degenerate signal — never presented
  // as confident output. This corpus is known-seeded-thin (per memory), so
  // this branch is expected to trigger on the real "Programming & Software
  // Books" project, not just in tests.
  const distinctLabels = new Set(clusterList.map((c) => c.label)).size;
  const lowSignalClusters = clusterList.length > 0 && (clusterList.length <= 2 || distinctLabels <= 1);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 py-6">
      <div className="flex flex-col gap-1">
        <h1 className="display text-3xl text-[var(--ink)]">
          {projectData?.name ?? "Niche Dashboard"}
        </h1>
        <p className="text-sm text-[var(--muted)]">
          Browsing the seeded historical corpus for this niche.
        </p>
      </div>

      {/* 1. Summary KPIs */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Kpi label="Works" value={workList.length} />
        <Kpi label="Reviews" value={totalReviews} />
        <Kpi label="Clusters" value={clusterList.length} />
        <Kpi label="Gap candidates" value={candidateList.length} />
      </div>

      {/* 2. Top works */}
      <Card className="flex flex-col gap-4">
        <h2 className="display text-lg text-[var(--ink)]">Works</h2>
        {workList.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No works in this project yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
                  <th className="py-2 pr-3 font-medium">Title</th>
                  <th className="py-2 pr-3 font-medium">Author</th>
                  <th className="py-2 pr-3 font-medium">Rating</th>
                  <th className="py-2 pr-3 font-medium">Reviews</th>
                </tr>
              </thead>
              <tbody>
                {workList.map((w) => (
                  <WorkRow key={w.id} work={w} projectId={projectId} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 3. Niche-level complaint clusters */}
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="display text-lg text-[var(--ink)]">
            Niche-level complaint clusters
          </h2>
          {lowSignalClusters ? <FlagBadge flag="low_signal" /> : null}
        </div>
        {clusterList.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">
            No niche-level complaint clusters yet &mdash; interpret the corpus as
            thin until more reviews are seeded.
          </p>
        ) : (
          <>
            {lowSignalClusters ? (
              <p className="text-sm text-[var(--muted)]">
                low signal: {clusterList.length} cluster
                {clusterList.length === 1 ? "" : "s"}
                {distinctLabels <= 1 ? ", all one label" : ""} &mdash; interpret
                cautiously, not as a confident map of the niche.
              </p>
            ) : null}
            <ul className="flex flex-col gap-3">
              {clusterList.map((cluster) => (
                <ClusterRow key={cluster.id} cluster={cluster} />
              ))}
            </ul>
          </>
        )}
      </Card>

      {/* 4. Gap candidates */}
      <Card className="flex flex-col gap-4">
        <h2 className="display text-lg text-[var(--ink)]">Gap candidates</h2>
        {candidateList.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">
            No gap candidates scored yet &mdash; run a sweep to surface them.
          </p>
        ) : (
          <ol className="flex flex-col gap-3">
            {candidateList.map((c, i) => (
              <CandidateRow key={`${c.scope}-${c.ref_id}`} candidate={c} rank={i + 1} />
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: number }) {
  return (
    <Card className="flex flex-col gap-1 p-4">
      <span className="data text-2xl text-[var(--ink)]">{value}</span>
      <span className="text-xs text-[var(--muted)]">{label}</span>
    </Card>
  );
}

function WorkRow({ work, projectId }: { work: WorkOut; projectId: string }) {
  return (
    <tr className="border-b border-[var(--border)] last:border-b-0">
      <td className="py-2 pr-3">
        <Link
          href={`/p/${projectId}/works/${work.id}`}
          className="font-medium text-[var(--ink)] hover:text-[var(--ultramarine)]"
        >
          {work.title}
        </Link>
      </td>
      <td className="py-2 pr-3 text-[var(--muted)]">{work.author ?? "Unknown"}</td>
      <td className="data py-2 pr-3 text-[var(--ink)]">
        {work.agg_rating_avg !== null ? (
          <>
            {work.agg_rating_avg.toFixed(1)}
            <span className="text-[var(--muted)]"> ({work.agg_rating_count ?? 0})</span>
          </>
        ) : (
          <span className="text-[var(--muted)]">No rating</span>
        )}
      </td>
      <td className="data py-2 pr-3 text-[var(--ink)]">{work.review_count}</td>
    </tr>
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

function CandidateRow({ candidate, rank }: { candidate: CandidateOut; rank: number }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-3 last:border-b-0 last:pb-0">
      <div className="flex items-center gap-3">
        <span className="data text-xs text-[var(--muted)]">#{rank}</span>
        <span className="text-sm font-medium text-[var(--ink)]">{candidate.title}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="data text-sm text-[var(--ink)]">
          {candidate.gap_score.toFixed(2)}
        </span>
        <span className="data text-xs text-[var(--muted)]">
          {(candidate.confidence * 100).toFixed(0)}% conf.
        </span>
        {candidate.incomplete ? <FlagBadge flag="incomplete" /> : null}
        {candidate.blind_spot ? <FlagBadge flag="blind_spot" /> : null}
      </div>
    </li>
  );
}
