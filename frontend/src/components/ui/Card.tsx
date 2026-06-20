import { HTMLAttributes } from "react";

export function Card({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-lg border border-[var(--border)] bg-[var(--panel)] p-6 shadow-sm ${className}`}
      {...rest}
    />
  );
}
