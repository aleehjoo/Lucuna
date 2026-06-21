"use client";

import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
import { ResponsiveContainer } from "recharts";
import { ChartFrame } from "./ChartFrame";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { CandidateOut } from "@/lib/types";

// Paired bars per candidate: demand_score vs supply_scarcity. Per §7/§12,
// "demand" here is a popularity PROXY (ratings/read counts/NYT presence) —
// never unit sales or BSR — so that caveat is rendered as a permanent label
// in this panel, not a tooltip an operator can miss.
export function DemandSupply({ candidates }: { candidates: CandidateOut[] }) {
  const reducedMotion = useReducedMotion();
  const data = candidates.map((c) => ({
    name: c.title,
    demand: c.demand_score,
    supply: c.supply_scarcity,
  }));

  return (
    <ChartFrame
      title="Demand vs. supply scarcity"
      provenance={data.length > 0 ? `${data.length} candidate${data.length === 1 ? "" : "s"}` : undefined}
      isEmpty={data.length === 0}
      emptyTitle="No candidates scored yet"
      emptyMessage="Run a sweep (or seed this niche) to score demand and supply scarcity for candidates."
    >
      <p className="text-xs text-[var(--muted)]">
        Demand is a popularity proxy (ratings, read counts, bestseller presence) —{" "}
        <span className="font-medium text-[var(--ink)]">not sales or revenue</span>.
      </p>
      {/* Accessible row list — see AspectFrequency for why: Recharts wraps
          long Y-axis category names across multiple <tspan> lines, which
          screen readers (and exact-text test assertions) can't reliably
          read as one string. */}
      <ul className="sr-only" data-testid="demand-supply-rows">
        {data.map((d) => (
          <li key={d.name}>
            {d.name}: demand {d.demand.toFixed(2)}, supply scarcity {d.supply.toFixed(2)}
          </li>
        ))}
      </ul>
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 56)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 24, bottom: 4, left: 16 }}
        >
          <CartesianGrid stroke="var(--border)" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 1]}
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fontSize: 11, fill: "var(--muted)" }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={200}
            tick={{ fontSize: 12, fill: "var(--ink)" }}
          />
          <Tooltip
            formatter={(value) => (typeof value === "number" ? value.toFixed(2) : value)}
            contentStyle={{
              background: "var(--panel)",
              border: "1px solid var(--border)",
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar
            name="Demand (proxy)"
            dataKey="demand"
            fill="var(--ultramarine)"
            radius={[0, 4, 4, 0]}
            isAnimationActive={!reducedMotion}
          />
          <Bar
            name="Supply scarcity"
            dataKey="supply"
            fill="var(--oxblood)"
            radius={[0, 4, 4, 0]}
            isAnimationActive={!reducedMotion}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
