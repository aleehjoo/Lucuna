import { ReactNode } from "react";

// Shared shell for every chart in this directory: a title, an optional
// provenance line (mono, right-aligned), and the plot area below. Centralizes
// the "never a blank box" rule — callers pass `isEmpty` + `emptyMessage` and
// get an honest, identity-styled empty state instead of an empty SVG.
export function ChartFrame({
  title,
  provenance,
  isEmpty,
  emptyTitle,
  emptyMessage,
  children,
}: {
  title: string;
  provenance?: ReactNode;
  isEmpty: boolean;
  emptyTitle?: string;
  emptyMessage: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="display text-base text-[var(--ink)]">{title}</h3>
        {provenance ? (
          <span className="data text-xs text-[var(--muted)]">{provenance}</span>
        ) : null}
      </div>
      {isEmpty ? (
        <div className="flex flex-col items-center gap-1 rounded-md border border-dashed border-[var(--border)] px-4 py-8 text-center">
          {emptyTitle ? (
            <p className="text-sm font-medium text-[var(--ink)]">{emptyTitle}</p>
          ) : null}
          <p className="max-w-sm text-sm text-[var(--muted)]">{emptyMessage}</p>
        </div>
      ) : (
        children
      )}
    </div>
  );
}
