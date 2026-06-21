import { Chip } from "@/components/ui/Chip";

// Sample-size + platform + (date-range, if available) chips — the
// provenance strip that travels with every chart per §7 ("never imply more
// certainty than the sample supports"). Not a Recharts visualization itself,
// but lives alongside the other charts since every other chart in this
// directory composes it as a caption.
//
// `oldestSignal`/`newestSignal` carry the timely<->evergreen freshness
// dimension (PRD §10's `oldest_signal`/`newest_signal`): when the newest
// signal is old, the date-range chip is dimmed to read as stale rather than
// current, without inventing a "stale" flag that doesn't exist on the data.
export function ProvenanceChips({
  sampleSize,
  platforms,
  oldestSignal,
  newestSignal,
}: {
  sampleSize: number;
  platforms: string[];
  oldestSignal?: string | null;
  newestSignal?: string | null;
}) {
  const hasDateRange = !!oldestSignal && !!newestSignal;
  const stale = hasDateRange && isStale(newestSignal);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Chip mono>n={sampleSize}</Chip>
      {platforms.length === 0 ? (
        <span className="text-xs text-[var(--muted)]">No platform provenance recorded.</span>
      ) : (
        platforms.map((p) => (
          <Chip key={p} mono>
            {p}
          </Chip>
        ))
      )}
      {hasDateRange ? (
        <Chip mono className={stale ? "opacity-50" : undefined}>
          {formatDate(oldestSignal)}&ndash;{formatDate(newestSignal)}
          {stale ? " (stale)" : ""}
        </Chip>
      ) : null}
    </div>
  );
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "?";
  return iso.slice(0, 10);
}

// "Stale" here means the freshest signal is >18 months old — the same
// threshold the Context Pack's instructions_to_model use to tell a
// downstream LLM to down-weight a candidate (PRD §12).
function isStale(newestSignal: string | null | undefined): boolean {
  if (!newestSignal) return false;
  const newest = new Date(newestSignal).getTime();
  if (Number.isNaN(newest)) return false;
  const eighteenMonthsMs = 18 * 30 * 24 * 60 * 60 * 1000;
  return Date.now() - newest > eighteenMonthsMs;
}
