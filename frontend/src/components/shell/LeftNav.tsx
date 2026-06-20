"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS = [
  { key: "search", label: "Search" },
  { key: "dashboard", label: "Niche Dashboard" },
  { key: "sweep", label: "Category Sweep" },
  { key: "seed", label: "Seed & Data" },
  { key: "settings", label: "Settings" },
] as const;

// Pulls the current project id (if any) out of the pathname, e.g.
// /p/abc123/dashboard -> "abc123". Outside a project context (e.g. "/") this
// is null and the nav still renders, just without a destination yet.
function projectIdFromPathname(pathname: string | null): string | null {
  const match = pathname?.match(/^\/p\/([^/]+)/);
  return match ? match[1] : null;
}

export function LeftNav() {
  const pathname = usePathname();
  const projectId = projectIdFromPathname(pathname);

  return (
    <nav
      aria-label="Workspace sections"
      className="flex w-56 flex-col gap-1 border-r border-[var(--border)] bg-[var(--paper)] p-3"
    >
      {SECTIONS.map((section) => {
        const href = projectId ? `/p/${projectId}/${section.key}` : "#";
        const active = pathname?.startsWith(`/p/${projectId}/${section.key}`);
        return (
          <Link
            key={section.key}
            href={href}
            aria-current={active ? "page" : undefined}
            aria-disabled={!projectId}
            className={`rounded-md px-3 py-2 text-sm transition ${
              active
                ? "bg-[color-mix(in_srgb,var(--ultramarine)_10%,transparent)] font-medium text-[var(--ultramarine)]"
                : projectId
                  ? "text-[var(--ink)] hover:bg-[color-mix(in_srgb,var(--ink)_5%,transparent)]"
                  : "text-[var(--muted)]"
            }`}
          >
            {section.label}
          </Link>
        );
      })}
    </nav>
  );
}
