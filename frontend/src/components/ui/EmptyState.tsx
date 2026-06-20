import { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-[var(--border)] px-6 py-12 text-center">
      <p className="display text-lg text-[var(--ink)]">{title}</p>
      {description ? (
        <p className="max-w-md text-sm text-[var(--muted)]">{description}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
