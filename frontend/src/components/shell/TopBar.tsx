"use client";

import { useHealth } from "@/lib/hooks";
import { ProjectSwitcher } from "./ProjectSwitcher";

// Quiet status dot + copy. Warming uses a soft gold pulse (not red/alarming —
// this is an expected one-time cost on cold start, not an error). Ready uses
// a small ultramarine dot; no pulse, no chatter.
function HealthIndicator() {
  const { data, isLoading } = useHealth();
  const ready = data?.models_ready ?? false;

  if (isLoading && !data) {
    return (
      <span className="data flex items-center gap-2 text-xs text-[var(--muted)]">
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--muted)]" />
        connecting…
      </span>
    );
  }

  if (!ready) {
    return (
      <span
        className="data flex items-center gap-2 text-xs text-[var(--muted)]"
        title="Local models (embeddings, clustering, zero-shot labeling) are loading. This happens once per backend start."
      >
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--gold-leaf)]" />
        warming up the analysis engine…
      </span>
    );
  }

  return (
    <span
      className="data flex items-center gap-2 text-xs text-[var(--muted)]"
      title="Local NLP models are warm and ready."
    >
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--ultramarine)]" />
      engine ready
    </span>
  );
}

export function TopBar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--panel)] px-4">
      <div className="flex items-center gap-4">
        <span className="display text-lg tracking-tight text-[var(--ink)]">
          Lacuna
        </span>
        <ProjectSwitcher />
      </div>
      <HealthIndicator />
    </header>
  );
}
