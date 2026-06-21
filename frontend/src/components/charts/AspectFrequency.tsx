"use client";

import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { ResponsiveContainer } from "recharts";
import { ChartFrame } from "./ChartFrame";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { ClusterOut, LiveSearchClusterOut } from "@/lib/types";

type Aspect = ClusterOut | LiveSearchClusterOut;

// The core "what readers complain about" view — a horizontal bar per
// clustered aspect, ranked by reviewer_count (the only volume signal these
// clusters carry; there is no separate "frequency" field to chart). Accepts
// either persisted ClusterOut rows (Dashboard) or the live-search
// LiveSearchClusterOut shape (Search result) — both carry label,
// reviewer_count, platforms, cross_platform.
export function AspectFrequency({
  clusters,
  title = "What readers complain about",
}: {
  clusters: Aspect[];
  title?: string;
}) {
  const reducedMotion = useReducedMotion();
  const sorted = [...clusters].sort((a, b) => b.reviewer_count - a.reviewer_count);
  const data = sorted.map((c) => ({
    name: c.label,
    reviewers: c.reviewer_count,
    crossPlatform: c.cross_platform,
  }));
  const totalReviewers = sorted.reduce((sum, c) => sum + c.reviewer_count, 0);

  return (
    <ChartFrame
      title={title}
      provenance={
        data.length > 0 ? `${data.length} aspect${data.length === 1 ? "" : "s"} · ${totalReviewers} reviewer${totalReviewers === 1 ? "" : "s"}` : undefined
      }
      isEmpty={data.length === 0}
      emptyTitle="No complaint clusters yet"
      emptyMessage="Not enough reviews have clustered into distinct aspects yet — interpret this niche as thin until more signal arrives."
    >
      {/* Accessible row list — screen readers (and Recharts-in-jsdom tests)
          can't reliably parse SVG tick labels, which Recharts wraps across
          multiple <tspan> lines for long names. This list carries the exact
          same ranked data as plain, unsplit text. */}
      <ul className="sr-only">
        {data.map((d) => (
          <li key={d.name}>
            {d.name}: {d.reviewers} reviewer{d.reviewers === 1 ? "" : "s"}
            {d.crossPlatform ? ", cross-platform" : ""}
          </li>
        ))}
      </ul>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 44)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 24, bottom: 4, left: 16 }}
        >
          <CartesianGrid stroke="var(--border)" horizontal={false} />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fontSize: 11, fill: "var(--muted)" }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={200}
            tick={{ fontSize: 12, fill: "var(--ink)" }}
          />
          <Tooltip
            formatter={(value) => [`${value} reviewers`, "Mentions"]}
            contentStyle={{
              background: "var(--panel)",
              border: "1px solid var(--border)",
              fontSize: 12,
            }}
          />
          <Bar
            dataKey="reviewers"
            fill="var(--ultramarine)"
            radius={[0, 4, 4, 0]}
            isAnimationActive={!reducedMotion}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
