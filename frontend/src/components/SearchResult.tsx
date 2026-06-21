"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { FlagBadge } from "@/components/ui/FlagBadge";
import type { LiveSearchCounts } from "@/lib/types";

// THE DESIGN CONSTRAINT (product owner, non-negotiable): live single-title
// search routinely returns 0 complaint clusters — proven at the W4 gate
// ("Atomic Habits" = 50 reviews, 0 clusters). This component must stay
// genuinely useful when that happens. Render order is fixed:
//   1. resolved title
//   2. sample/confidence summary (NOT a fabricated star rating — Hardcover's
//      live search path only ever surfaces a critical-review sample size and
//      a derived confidence score; see the "no rating" note below)
//   3. provenance (platforms, review count, fresh-only vs historical+fresh)
//   4. validity flags (incomplete / blind_spot / fresh_only)
//   5. clusters — a BONUS section, only ever below the above, and replaced
//      with an honest low_signal note (never a blank panel) when empty.
//   6. Context Pack download.
//
// NOTE on "rating summary": the backend's live-search payload
// (lacuna/pipeline/live_single_title.analyze_live) does not currently
// compute or return an aggregate star rating — only a critical-review
// (rating <= 3) sample used for clustering. Surfacing a numeric rating here
// would mean inventing data the API never sends. Instead this summarizes
// honestly with what the payload actually carries: review_count, the
// critical-review sample size that fed clustering, and the resulting
// confidence — flagged as a known gap in the task report.
export function SearchResult({ counts }: { counts: LiveSearchCounts }) {
  if (counts.not_found) {
    return (
      <EmptyState
        title="Couldn't resolve that title"
        description="Hardcover didn't return a match for this title or ISBN. Check the spelling, try the author's name, or try the ISBN directly."
      />
    );
  }

  const candidate = counts.pack.candidates[0];
  const platforms = candidate?.validity.platforms ?? [];
  const sampleSize = candidate?.validity.sample_size ?? 0;
  const confidence = candidate?.validity.confidence ?? 0;
  const hasClusters = counts.clusters.length > 0;

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Resolved title + provenance + sample/confidence summary — always
          present, always above the fold, never gated on clusters existing. */}
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 className="display text-2xl text-[var(--ink)]">{counts.title}</h2>
            <p className="data text-sm text-[var(--muted)]">
              {counts.review_count} review{counts.review_count === 1 ? "" : "s"} pulled
              live from Hardcover &middot; {sampleSize} critical (&le;3&#9733;) in the
              sample that fed clustering
            </p>
          </div>
          <FlagBadge flag={counts.fresh_only ? "fresh_only" : "incomplete"} />
        </div>

        {/* Provenance line — platforms + fresh-only vs historical+fresh, per
            THE DESIGN CONSTRAINT (priority #3, but rendered together with the
            summary since both come from the same Card). */}
        <div className="flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-3">
          {platforms.map((p) => (
            <Chip key={p} mono>
              {p}
            </Chip>
          ))}
          <span className="text-sm text-[var(--muted)]">
            {counts.fresh_only
              ? "No historical depth — live Hardcover only."
              : "Historical seeded corpus + live Hardcover, merged."}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="data text-xs text-[var(--muted)]">
            Confidence {(confidence * 100).toFixed(0)}%
          </span>
          {candidate?.validity.incomplete ? <FlagBadge flag="incomplete" /> : null}
          {candidate?.validity.blind_spot ? <FlagBadge flag="blind_spot" /> : null}
          {candidate?.validity.recent_supply_surge ? (
            <FlagBadge flag="recent_supply_surge" />
          ) : null}
        </div>
      </Card>

      {/* 5. Clusters — a BONUS section. Never the spine of the result: when
          empty, an honest low_signal note replaces it, and everything above
          this point has already given the operator a complete result. */}
      {hasClusters ? (
        <Card className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="display text-lg text-[var(--ink)]">
              Complaint clusters
            </h3>
            <span className="data text-xs text-[var(--muted)]">
              cross-platform agreement {(counts.agreement_pct * 100).toFixed(0)}%
            </span>
          </div>
          <ul className="flex flex-col gap-3">
            {counts.clusters.map((cluster, i) => (
              <li
                key={`${cluster.label}-${i}`}
                className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] pb-3 last:border-b-0 last:pb-0"
              >
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-[var(--ink)]">
                    {cluster.label}
                  </span>
                  <span className="text-xs text-[var(--muted)]">
                    {cluster.reviewer_count} reviewer
                    {cluster.reviewer_count === 1 ? "" : "s"}
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
            ))}
          </ul>
        </Card>
      ) : (
        <div className="flex items-center gap-3 rounded-lg border border-[var(--border)] px-4 py-3">
          <FlagBadge flag="low_signal" />
          <p className="text-sm text-[var(--muted)]">
            low signal: {counts.review_count} review
            {counts.review_count === 1 ? "" : "s"}, no distinct complaint
            clusters &mdash; interpret cautiously
          </p>
        </div>
      )}

      {/* 6. Context Pack download. */}
      <div className="flex justify-end">
        <Button variant="ghost" onClick={() => downloadPack(counts)}>
          Download Context Pack (JSON)
        </Button>
      </div>
    </div>
  );
}

// Downloads the pack that's already in this job's counts — NOT a fresh call
// to GET /export, which regenerates a category_sweep pack scoped to the
// project's seeded corpus and would return a different (unrelated) pack, not
// this title's single-candidate result.
function downloadPack(counts: LiveSearchCounts) {
  const blob = new Blob([JSON.stringify(counts.pack, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const safeName = counts.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  a.download = `context-pack-${safeName || "search"}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
