"use client";

import Link from "next/link";
import { ProjectCard } from "@/components/ProjectCard";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useProjects } from "@/lib/hooks";

// The real Projects home (replaces the W5 design-preview landing). Every
// niche the operator runs lives here — grid of cards, or a guided onboarding
// flow on first run. No dead ends: loading, error, and empty all resolve to
// a state with a clear next action (Frontend PRD §8, §11).
export default function ProjectsPage() {
  const { data: projects, isLoading, isError, refetch } = useProjects();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 py-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="display text-3xl text-[var(--ink)]">Projects</h1>
          <p className="text-sm text-[var(--muted)]">
            Each project is an isolated niche &mdash; its own corpus, clusters,
            and gap candidates.
          </p>
        </div>
        {projects && projects.length > 0 ? (
          <Link href="/projects/new">
            <Button variant="primary">New project</Button>
          </Link>
        ) : null}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState
          message="Couldn't load your projects."
          onRetry={() => refetch()}
        />
      ) : !projects || projects.length === 0 ? (
        <EmptyState
          title="Create your first project"
          description="A project seeds a corpus for one niche, runs the local NLP pipeline on it, and surfaces the gaps between reader demand and what's actually in print. Nothing leaves your machine until you ask it to."
          action={
            <Link href="/projects/new">
              <Button variant="primary">Create your first project</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  );
}
