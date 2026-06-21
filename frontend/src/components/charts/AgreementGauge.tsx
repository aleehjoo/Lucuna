"use client";

import { Bar, BarChart, Tooltip, XAxis, YAxis } from "recharts";
import { ResponsiveContainer } from "recharts";
import { ChartFrame } from "./ChartFrame";
import { useReducedMotion } from "@/lib/useReducedMotion";

// Cross-platform agreement % — the credibility signal from §9: a complaint
// confirmed on more than one platform is weighted more heavily. Rendered as
// a single horizontal fill bar (not a circular gauge) so it stays legible at
// small sizes and degrades cleanly to text when there's no signal to show.
//
// `sampleSize === 0` is the degenerate case (no candidate/result to compute
// agreement from at all) — distinct from a real 0% agreement, which DOES
// render (a real measured disagreement is information, not an absence).
export function AgreementGauge({
  agreementPct,
  sampleSize,
}: {
  agreementPct: number;
  sampleSize: number;
}) {
  const reducedMotion = useReducedMotion();
  const pct = Math.round(agreementPct * 100);
  const data = [{ name: "agreement", value: agreementPct, rest: 1 - agreementPct }];

  return (
    <ChartFrame
      title="Cross-platform agreement"
      provenance={sampleSize > 0 ? `n=${sampleSize}` : undefined}
      isEmpty={sampleSize === 0}
      emptyTitle="No agreement signal yet"
      emptyMessage="Cross-platform agreement needs complaints observed on more than one platform — none recorded yet."
    >
      <div className="flex items-center gap-4">
        <ResponsiveContainer width="100%" height={48}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
          >
            <XAxis type="number" domain={[0, 1]} hide />
            <YAxis type="category" dataKey="name" hide />
            <Tooltip
              formatter={() => [`${pct}%`, "Agreement"]}
              contentStyle={{
                background: "var(--panel)",
                border: "1px solid var(--border)",
                fontSize: 12,
              }}
            />
            <Bar
              dataKey="value"
              fill="var(--ultramarine)"
              radius={[6, 6, 6, 6]}
              barSize={20}
              isAnimationActive={!reducedMotion}
            />
          </BarChart>
        </ResponsiveContainer>
        <span className="data shrink-0 text-2xl text-[var(--ink)]">{pct}%</span>
      </div>
    </ChartFrame>
  );
}
