"use client";

import type { ReactNode } from "react";
import { Bar, BarChart, Tooltip, XAxis, YAxis } from "recharts";
import { ResponsiveContainer } from "recharts";
import type { TooltipContentProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { CandidateOut } from "@/lib/types";

// THE SIGNATURE CHART. Thesis: "the opportunity is the negative space." Each
// row is a candidate's full [0,1] market track. The gold-leaf segment is the
// UNFILLED gap (gap_score) — bigger void = bigger opportunity, an inverted
// fill semantic from a typical "progress" bar where filled=more. The muted
// remainder behind it is the "served" track, drawn via Bar's `background`
// prop so the full row width is always present (never an empty SVG row).
// Confidence drives the gold segment's opacity — a high-gap, low-confidence
// candidate reads as a paler void, not a confident, solid claim.
//
// DEGENERATE-DATA REALITY: in the current corpus-only seed every candidate's
// gap_score is 0.0 (demand is withheld in a $0 corpus-only run — see
// Lacuna_PRD.md §10's missing-data rule). A naive render of this chart against
// that data would be a row of zero-width gold slivers: visually indistinguishable
// from "this niche has zero opportunity," when the truth is "we have no demand
// signal to compute gap from yet." That false impression is worse than no chart
// at all, so this component checks for real variation across candidates BEFORE
// rendering bars at all, and substitutes an explicit, honest note when there is
// none — never a row of invisible bars.
export function GapStrip({ candidates }: { candidates: CandidateOut[] }) {
  const reducedMotion = useReducedMotion();

  if (candidates.length === 0) {
    return (
      <GapStripFrame>
        <EmptyNote
          title="No gap candidates yet"
          message="Run a sweep (or seed this niche) to score gap candidates."
        />
      </GapStripFrame>
    );
  }

  // Real variation = at least one candidate has a genuinely nonzero gap_score.
  // Per PRD §10, a genuine zero IS allowed to propagate (e.g. a truly
  // saturated shelf) — but ALL candidates landing on exactly 0.0 in the
  // current seed is the withheld-demand case, not N independent genuine
  // zeros, so the all-zero case gets the degenerate branch below.
  const hasVariation = candidates.some((c) => c.gap_score > 0);

  if (!hasVariation) {
    return (
      <GapStripFrame>
        <EmptyNote
          title="Gap map not yet populated"
          message="Gap scores need demand signals, which aren't present in a $0 corpus-only run. Seed demand sources (or run a live search) to populate the gap map."
        />
      </GapStripFrame>
    );
  }

  const data = candidates.map((c) => ({
    name: c.title,
    gap: c.gap_score,
    confidence: c.confidence,
    sampleSize: c.sample_size,
    platforms: c.platforms_used,
  }));

  return (
    <GapStripFrame provenance={`${data.length} candidate${data.length === 1 ? "" : "s"}`}>
      {/* Accessible row list — the gold-void bar's gap% label is rendered as
          an SVG <text> split across separate "NN" and "% gap" text nodes
          (Recharts/SVG text layout), which screen readers (and exact-text
          test assertions) can't reliably read as one string. This list
          carries the same per-candidate data as plain, unsplit text. */}
      <ul className="sr-only">
        {data.map((d) => (
          <li key={d.name}>
            {d.name}: {Math.round(d.gap * 100)}% gap, confidence{" "}
            {Math.round(d.confidence * 100)}%, n={d.sampleSize}
            {d.platforms.length > 0 ? `, ${d.platforms.join(", ")}` : ""}
          </li>
        ))}
      </ul>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 48)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 56, bottom: 4, left: 16 }}
        >
          <XAxis type="number" domain={[0, 1]} hide />
          <YAxis
            type="category"
            dataKey="name"
            width={200}
            tick={{ fontSize: 12, fill: "var(--ink)" }}
          />
          <Tooltip content={GapTooltip} />
          <Bar
            dataKey="gap"
            background={{ fill: "var(--border)", radius: 4 }}
            radius={[4, 4, 4, 4]}
            isAnimationActive={!reducedMotion}
            shape={(props: GapBarShapeProps) => <GapBarShape {...props} />}
            label={(props: GapLabelProps) => <GapBarLabel {...props} />}
          />
        </BarChart>
      </ResponsiveContainer>
    </GapStripFrame>
  );
}

function GapStripFrame({
  provenance,
  children,
}: {
  provenance?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="display text-base text-[var(--ink)]">Gap map</h3>
        {provenance ? (
          <span className="data text-xs text-[var(--muted)]">{provenance}</span>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function EmptyNote({ title, message }: { title: string; message: string }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-md border border-dashed border-[var(--border)] px-4 py-8 text-center">
      <p className="text-sm font-medium text-[var(--ink)]">{title}</p>
      <p className="max-w-md text-sm text-[var(--muted)]">{message}</p>
    </div>
  );
}

// --- Per-row gold-void rendering -------------------------------------------
//
// `Cell` is deprecated in Recharts 3.x (removed in 4.0) in favor of the
// `shape`/`label` render-prop path used here, per Context7's current docs
// (recharts/src/component/Cell.tsx deprecation notice).

interface GapBarDatum {
  name: string;
  gap: number;
  confidence: number;
  sampleSize: number;
  platforms: string[];
}

interface GapBarShapeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: GapBarDatum;
}

function GapBarShape({ x = 0, y = 0, width = 0, height = 0, payload }: GapBarShapeProps) {
  const confidence = payload?.confidence ?? 0;
  // Confidence-shaded opacity: a low-confidence gap reads as a paler void,
  // never as solid/confident as a well-evidenced one. Floor of 0.35 keeps
  // even a near-zero-confidence gap visible (per §10/§7: never imply more —
  // or less — certainty than the sample supports; a faint void still IS one).
  const opacity = 0.35 + 0.65 * confidence;
  return (
    <rect
      x={x}
      y={y}
      width={width}
      height={height}
      rx={4}
      ry={4}
      fill="var(--gold-leaf)"
      fillOpacity={opacity}
    />
  );
}

interface GapLabelProps {
  x?: string | number;
  y?: string | number;
  width?: string | number;
  height?: string | number;
  value?: string | number | boolean | null;
}

// Label rendered just past the end of each gold segment: gap% plus the
// provenance the brief calls for inline (n, platform count) — visible at a
// glance, not hidden behind a hover-only tooltip.
function GapBarLabel({ x, y, width, height, value }: GapLabelProps) {
  const numX = Number(x ?? 0);
  const numY = Number(y ?? 0);
  const numWidth = Number(width ?? 0);
  const numHeight = Number(height ?? 0);
  const numValue = Number(value);
  if (
    value === undefined ||
    value === null ||
    typeof value === "boolean" ||
    Number.isNaN(numValue)
  )
    return null;
  return (
    <text
      x={numX + numWidth + 8}
      y={numY + numHeight / 2}
      dy={4}
      fontSize={11}
      fontFamily="var(--font-plex-mono), ui-monospace, monospace"
      fill="var(--muted)"
    >
      {Math.round(numValue * 100)}% gap
    </text>
  );
}

function GapTooltip({ active, payload }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload || payload.length === 0) return null;
  const datum = payload[0]?.payload as GapBarDatum | undefined;
  if (!datum) return null;
  return (
    <div
      className="data rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-xs"
      style={{ fontSize: 12 }}
    >
      <p className="font-medium text-[var(--ink)]">{datum.name}</p>
      <p className="text-[var(--muted)]">
        gap {(datum.gap * 100).toFixed(0)}% · confidence {(datum.confidence * 100).toFixed(0)}%
      </p>
      <p className="text-[var(--muted)]">
        n={datum.sampleSize}
        {datum.platforms.length > 0 ? ` · ${datum.platforms.join(", ")}` : ""}
      </p>
    </div>
  );
}
