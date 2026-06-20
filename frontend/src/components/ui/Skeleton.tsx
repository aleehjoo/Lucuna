import { HTMLAttributes } from "react";

export function Skeleton({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-[color-mix(in_srgb,var(--ink)_8%,transparent)] ${className}`}
      {...rest}
    />
  );
}
