import { HTMLAttributes } from "react";

export type Flag =
  | "incomplete"
  | "blind_spot"
  | "recent_supply_surge"
  | "fresh_only"
  | "low_signal";

const LABEL: Record<Flag, string> = {
  incomplete: "Incomplete",
  blind_spot: "Blind spot",
  recent_supply_surge: "Supply surging",
  fresh_only: "Fresh only",
  low_signal: "Low signal",
};

const TOOLTIP: Record<Flag, string> = {
  incomplete:
    "A data layer failed or is missing, so this score is withheld or imputed — never silently treated as zero.",
  blind_spot:
    "Thin data here — there may be a survivorship gap we can't see past.",
  recent_supply_surge:
    "New titles have rushed into this category since 2023 — this gap may already be closing.",
  fresh_only:
    "No historical depth — live Hardcover only.",
  low_signal:
    "Low signal: few reviews / one cluster — interpret cautiously.",
};

// muted | oxblood-solid | oxblood-outline | ultramarine-outline
const STYLE: Record<Flag, string> = {
  incomplete: "bg-[color-mix(in_srgb,var(--ink)_8%,transparent)] text-[var(--muted)] border border-transparent",
  blind_spot: "bg-[color-mix(in_srgb,var(--ink)_8%,transparent)] text-[var(--muted)] border border-transparent",
  recent_supply_surge: "bg-[var(--oxblood)] text-white border border-transparent",
  low_signal: "bg-transparent text-[var(--oxblood)] border border-[var(--oxblood)]",
  fresh_only: "bg-transparent text-[var(--ultramarine)] border border-[var(--ultramarine)]",
};

export function FlagBadge({
  flag,
  className = "",
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { flag: Flag }) {
  return (
    <span
      title={TOOLTIP[flag]}
      aria-label={`${LABEL[flag]}: ${TOOLTIP[flag]}`}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLE[flag]} ${className}`}
      {...rest}
    >
      {LABEL[flag]}
    </span>
  );
}
