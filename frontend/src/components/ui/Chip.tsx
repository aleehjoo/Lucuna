import { HTMLAttributes } from "react";

export function Chip({
  mono = false,
  className = "",
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { mono?: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border border-[var(--border)] px-2.5 py-0.5 text-xs text-[var(--muted)] ${
        mono ? "font-[var(--font-plex-mono)] tracking-tight" : "font-medium"
      } ${className}`}
      {...rest}
    />
  );
}
