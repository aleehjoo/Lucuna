"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useProjects } from "@/lib/hooks";

// GCP-console-style project switcher: a button showing the current/first
// project, opening a dropdown of all projects. Selecting one navigates to
// that project's dashboard. Handles empty/loading states without erroring.
export function ProjectSwitcher() {
  const { data: projects, isLoading, isError } = useProjects();
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickAway(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, [open]);

  function selectProject(id: string) {
    setOpen(false);
    router.push(`/p/${id}/dashboard`);
  }

  const label = isLoading
    ? "Loading projects…"
    : isError
      ? "Projects unavailable"
      : projects && projects.length > 0
        ? `${projects.length} project${projects.length === 1 ? "" : "s"}`
        : "No projects yet";

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-1.5 text-sm text-[var(--ink)] transition hover:bg-[color-mix(in_srgb,var(--ink)_5%,transparent)]"
      >
        <span className="data text-[var(--muted)]">{label}</span>
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="none"
          className={`h-3.5 w-3.5 text-[var(--muted)] transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path
            d="M5 7.5L10 12.5L15 7.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open ? (
        <div
          role="listbox"
          className="absolute left-0 z-20 mt-1 w-72 overflow-hidden rounded-md border border-[var(--border)] bg-[var(--panel)] shadow-lg"
        >
          <div className="border-b border-[var(--border)] px-3 py-2">
            <p className="text-xs font-medium text-[var(--muted)]">Switch project</p>
          </div>
          {isLoading ? (
            <p className="px-3 py-3 text-sm text-[var(--muted)]">Loading…</p>
          ) : isError ? (
            <p className="px-3 py-3 text-sm text-[var(--oxblood)]">
              Couldn&apos;t reach the backend.
            </p>
          ) : !projects || projects.length === 0 ? (
            <p className="px-3 py-3 text-sm text-[var(--muted)]">
              No projects yet — create one to get started.
            </p>
          ) : (
            <ul className="max-h-72 overflow-y-auto py-1">
              {projects.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    onClick={() => selectProject(p.id)}
                    className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm transition hover:bg-[color-mix(in_srgb,var(--ultramarine)_8%,transparent)]"
                  >
                    <span className="text-[var(--ink)]">{p.name}</span>
                    <span className="data text-xs text-[var(--muted)]">
                      {p.work_count} works · {p.cluster_count} clusters
                      {p.seeded ? "" : " · unseeded"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
