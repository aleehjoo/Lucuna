"use client";

import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import type { ProjectOut } from "@/lib/types";

// Renders a project's last-activity timestamp as a short, human date. Falls
// back to an honest "no activity yet" rather than inventing a date when the
// backend hasn't set created_at (e.g. a brand-new, unseeded project row).
function formatActivity(createdAt: string | null): string {
  if (!createdAt) return "No activity yet";
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return "No activity yet";
  return `Created ${date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })}`;
}

// One project per Card on the Projects home. Clicking anywhere on the card
// navigates into that project's dashboard — the card is the entry point into
// a niche's isolated workspace (PRD Frontend §9). Keyboard-operable (role
// "button" + Enter/Space) since the whole surface is clickable, not just a
// link buried inside it.
export function ProjectCard({ project }: { project: ProjectOut }) {
  const router = useRouter();

  function open() {
    router.push(`/p/${project.id}/dashboard`);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      open();
    }
  }

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={open}
      onKeyDown={onKeyDown}
      className="flex cursor-pointer flex-col gap-4 transition hover:border-[var(--ultramarine)] hover:shadow-md focus-visible:border-[var(--ultramarine)]"
    >
      <div className="flex flex-col gap-1">
        <h3 className="display text-xl text-[var(--ink)]">{project.name}</h3>
        <span
          className={`data text-xs ${
            project.seeded ? "text-[var(--ultramarine)]" : "text-[var(--muted)]"
          }`}
        >
          {project.seeded ? "Seeded" : "Not seeded yet"}
        </span>
      </div>

      {project.target_bisac.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {project.target_bisac.map((code) => (
            <Chip key={code} mono>
              {code}
            </Chip>
          ))}
        </div>
      ) : (
        <p className="text-sm text-[var(--muted)]">No BISAC codes set</p>
      )}

      <div className="flex items-center justify-between border-t border-[var(--border)] pt-3">
        <span className="data text-sm text-[var(--ink)]">
          {project.work_count} works &middot; {project.cluster_count} clusters
        </span>
        <span className="text-xs text-[var(--muted)]">
          {formatActivity(project.created_at)}
        </span>
      </div>
    </Card>
  );
}
