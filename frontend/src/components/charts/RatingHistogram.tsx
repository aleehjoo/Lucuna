"use client";

import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { ResponsiveContainer } from "recharts";
import { ChartFrame } from "./ChartFrame";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { RatingDistribution } from "@/lib/types";

const STARS = ["1", "2", "3", "4", "5"] as const;

// Distribution of ratings 1-5, fed by the live-search `rating_distribution`
// (or any equivalent per-work bucket map). Honors the "never a fabricated 0"
// rule from SearchResult: when `total` is 0 (no review in the pulled set
// carries a rating), this renders the honest empty state, not a row of
// zero-height bars.
export function RatingHistogram({
  distribution,
  total,
}: {
  distribution: RatingDistribution;
  total: number;
}) {
  const reducedMotion = useReducedMotion();
  const data = STARS.map((star) => ({
    star: `${star}★`,
    count: distribution[star],
  }));

  return (
    <ChartFrame
      title="Rating distribution"
      provenance={total > 0 ? `n=${total}` : undefined}
      isEmpty={total === 0}
      emptyTitle="No ratings available"
      emptyMessage="None of the pulled reviews carry a star rating yet — this isn't a zero rating, it's an absence of one."
    >
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="star" tick={{ fontSize: 12, fill: "var(--ink)" }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted)" }} />
          <Tooltip
            formatter={(value) => [`${value} review${value === 1 ? "" : "s"}`, "Count"]}
            contentStyle={{
              background: "var(--panel)",
              border: "1px solid var(--border)",
              fontSize: 12,
            }}
          />
          <Bar
            dataKey="count"
            fill="var(--gold-leaf)"
            radius={[4, 4, 0, 0]}
            isAnimationActive={!reducedMotion}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
