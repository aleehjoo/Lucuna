"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useProject, useUpdateProject } from "@/lib/hooks";

// Settings — intent knobs ONLY (Frontend PRD §10 / §13.10, acceptance §9).
//
// This surface persists a project's *intent* into its `config` JSONB column
// via PUT /projects/{id} — how this niche should be weighted/exported, never
// how the scoring math itself behaves. The two are deliberately split: intent
// knobs live here, in the UI, editable by any operator; correctness knobs
// (min_critical_per_work, shrinkage, gate epsilon, normalization method,
// crosswalk thresholds, model revisions) live only in `advanced.yaml` and are
// NEVER rendered anywhere in this product. Exposing them would let a user
// dial in whatever score they want — that defeats the point of having a
// validity-gated score at all. If you are reading this because you're about
// to add a field to this page, check it against that list first.
//
// Defaults below intentionally mirror the engine's own defaults
// (config/default.yaml region) so an unset config and an explicitly-saved
// default config produce identical behavior.
interface ConfigState {
  timely_evergreen: number;
  recency_months: number;
  export_max_candidates: number;
  export_token_budget: number;
}

const DEFAULTS: ConfigState = {
  timely_evergreen: 0.5,
  recency_months: 24,
  export_max_candidates: 20,
  export_token_budget: 8000,
};

function readConfig(config: Record<string, unknown> | undefined): ConfigState {
  const c = config ?? {};
  return {
    timely_evergreen:
      typeof c.timely_evergreen === "number" ? c.timely_evergreen : DEFAULTS.timely_evergreen,
    recency_months:
      typeof c.recency_months === "number" ? c.recency_months : DEFAULTS.recency_months,
    export_max_candidates:
      typeof c.export_max_candidates === "number"
        ? c.export_max_candidates
        : DEFAULTS.export_max_candidates,
    export_token_budget:
      typeof c.export_token_budget === "number"
        ? c.export_token_budget
        : DEFAULTS.export_token_budget,
  };
}

export default function SettingsPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const project = useProject(projectId);
  const updateProject = useUpdateProject(projectId);

  const [values, setValues] = useState<ConfigState>(DEFAULTS);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Load current values once the project resolves (and whenever a fresh
  // project payload arrives, e.g. after a save round-trips). Sensible
  // defaults fill in anything unset on the project's config.
  useEffect(() => {
    if (project.data) {
      setValues(readConfig(project.data.config));
    }
  }, [project.data]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaveError(null);
    setSaved(false);
    try {
      await updateProject.mutateAsync({ config: { ...values } });
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Couldn't save settings.");
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 py-6">
      <div className="flex flex-col gap-1">
        <h1 className="display text-3xl text-[var(--ink)]">Settings</h1>
        <p className="text-sm text-[var(--muted)]">
          Intent for this niche &mdash; how results are weighted and how much
          gets exported. These don&apos;t change how scores are computed.
        </p>
      </div>

      {project.isLoading ? (
        <Card className="flex flex-col gap-4">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </Card>
      ) : project.isError ? (
        <ErrorState
          message="Couldn't load project settings."
          onRetry={() => project.refetch()}
        />
      ) : (
        <Card>
          <form className="flex flex-col gap-6" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-2">
              <label
                htmlFor="settings-timely-evergreen"
                className="text-sm font-medium text-[var(--ink)]"
              >
                Timely &harr; evergreen
              </label>
              <input
                id="settings-timely-evergreen"
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={values.timely_evergreen}
                onChange={(e) =>
                  setValues((v) => ({ ...v, timely_evergreen: Number(e.target.value) }))
                }
                className="w-full accent-[var(--ultramarine)]"
              />
              <div className="flex justify-between text-xs text-[var(--muted)]">
                <span>Evergreen</span>
                <span className="data">{values.timely_evergreen.toFixed(1)}</span>
                <span>Timely</span>
              </div>
              <p className="text-xs text-[var(--muted)]">
                How much this niche favors recent signal over durable, all-time
                demand.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <label
                htmlFor="settings-recency-months"
                className="text-sm font-medium text-[var(--ink)]"
              >
                Recency window (months)
              </label>
              <input
                id="settings-recency-months"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                value={values.recency_months}
                onChange={(e) =>
                  setValues((v) => ({
                    ...v,
                    recency_months: Math.max(1, Number(e.target.value) || 0),
                  }))
                }
                className="data w-40 rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus-visible:border-[var(--ultramarine)]"
              />
              <p className="text-xs text-[var(--muted)]">
                How many months back count as &quot;recent&quot; signal for this
                niche.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <label
                htmlFor="settings-export-max-candidates"
                className="text-sm font-medium text-[var(--ink)]"
              >
                Export max candidates
              </label>
              <input
                id="settings-export-max-candidates"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                value={values.export_max_candidates}
                onChange={(e) =>
                  setValues((v) => ({
                    ...v,
                    export_max_candidates: Math.max(1, Number(e.target.value) || 0),
                  }))
                }
                className="data w-40 rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus-visible:border-[var(--ultramarine)]"
              />
              <p className="text-xs text-[var(--muted)]">
                Maximum number of gap candidates a Context Pack export
                includes.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <label
                htmlFor="settings-export-token-budget"
                className="text-sm font-medium text-[var(--ink)]"
              >
                Export token budget
              </label>
              <input
                id="settings-export-token-budget"
                type="number"
                inputMode="numeric"
                min={0}
                step={100}
                value={values.export_token_budget}
                onChange={(e) =>
                  setValues((v) => ({
                    ...v,
                    export_token_budget: Math.max(0, Number(e.target.value) || 0),
                  }))
                }
                className="data w-40 rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus-visible:border-[var(--ultramarine)]"
              />
              <p className="text-xs text-[var(--muted)]">
                Approximate token ceiling a Context Pack export should stay
                under.
              </p>
            </div>

            {saveError ? (
              <p className="text-sm text-[var(--oxblood)]">{saveError}</p>
            ) : null}
            {saved && !saveError ? (
              <p role="status" className="text-sm text-[var(--ultramarine)]">
                Settings saved.
              </p>
            ) : null}

            <div className="flex items-center justify-end gap-3">
              <Button type="submit" variant="primary" disabled={updateProject.isPending}>
                {updateProject.isPending ? "Saving…" : "Save settings"}
              </Button>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}
