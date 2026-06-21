"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { useCreateProject } from "@/lib/hooks";

// The validated BISAC set the engine is built and tested against (programming
// niche). Picking from this set — rather than free text — keeps a project's
// target_bisac inside the codes the corpus/crosswalk actually recognizes.
const VALIDATED_BISAC: { code: string; label: string }[] = [
  { code: "COM051000", label: "Programming / General" },
  { code: "COM051010", label: "Languages / General" },
  { code: "COM051360", label: "Languages / Python" },
  { code: "COM051230", label: "Software Development & Engineering" },
  { code: "COM060160", label: "Web Programming" },
];

// New Project — name, target BISAC, keywords, and a minimal intent-config
// default (timely<->evergreen). Creating a project does NOT seed it: seeding
// is a separate, explicit operator action on the Seed & Data surface
// (Frontend PRD §6.2). Only intent knobs live here — no correctness knobs
// (Frontend PRD §10).
export default function NewProjectPage() {
  const router = useRouter();
  const createProject = useCreateProject();

  const [name, setName] = useState("");
  const [selectedBisac, setSelectedBisac] = useState<string[]>([]);
  const [keywords, setKeywords] = useState("");
  const [timelyEvergreen, setTimelyEvergreen] = useState(0.5);

  const [nameError, setNameError] = useState<string | null>(null);
  const [bisacError, setBisacError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function toggleBisac(code: string) {
    setSelectedBisac((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitError(null);

    const trimmedName = name.trim();
    const hasNameError = trimmedName.length === 0;
    const hasBisacError = selectedBisac.length === 0;

    setNameError(hasNameError ? "Name the project before creating it." : null);
    setBisacError(
      hasBisacError ? "Select at least one BISAC code." : null,
    );
    if (hasNameError || hasBisacError) return;

    const keywordList = keywords
      .split(",")
      .map((k) => k.trim())
      .filter((k) => k.length > 0);

    try {
      const project = await createProject.mutateAsync({
        name: trimmedName,
        target_bisac: selectedBisac,
        subject_filter: keywordList.length > 0 ? { keywords: keywordList } : {},
        config: { timely_evergreen: timelyEvergreen },
      });
      router.push(`/p/${project.id}/dashboard`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Couldn't create the project.");
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 py-6">
      <div className="flex flex-col gap-1">
        <h1 className="display text-3xl text-[var(--ink)]">New project</h1>
        <p className="text-sm text-[var(--muted)]">
          A project is an isolated niche: its own corpus, clusters, and gap
          candidates. Creating it does not seed it — seeding is a separate
          step you trigger from Seed &amp; Data once the project exists.
        </p>
      </div>

      <Card>
        <form className="flex flex-col gap-6" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-2">
            <label htmlFor="project-name" className="text-sm font-medium text-[var(--ink)]">
              Name
            </label>
            <input
              id="project-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Programming"
              className="rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus-visible:border-[var(--ultramarine)]"
              aria-invalid={!!nameError}
              aria-describedby={nameError ? "project-name-error" : undefined}
            />
            {nameError ? (
              <p id="project-name-error" className="text-sm text-[var(--oxblood)]">
                {nameError}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-[var(--ink)]">Target BISAC</span>
            <p className="text-xs text-[var(--muted)]">
              Pick from the validated codes the engine recognizes. At least one is required.
            </p>
            <div className="flex flex-wrap gap-2">
              {VALIDATED_BISAC.map(({ code, label }) => {
                const selected = selectedBisac.includes(code);
                return (
                  <button
                    key={code}
                    type="button"
                    onClick={() => toggleBisac(code)}
                    aria-pressed={selected}
                    title={label}
                    className="rounded-full transition"
                  >
                    <Chip
                      mono
                      className={
                        selected
                          ? "border-[var(--ultramarine)] bg-[var(--ultramarine)] text-white"
                          : "hover:border-[var(--ultramarine)]"
                      }
                    >
                      {code}
                    </Chip>
                  </button>
                );
              })}
            </div>
            {bisacError ? (
              <p className="text-sm text-[var(--oxblood)]">{bisacError}</p>
            ) : null}
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="project-keywords" className="text-sm font-medium text-[var(--ink)]">
              Keywords <span className="text-[var(--muted)]">(optional)</span>
            </label>
            <input
              id="project-keywords"
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="comma-separated, e.g. python, async, testing"
              className="rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus-visible:border-[var(--ultramarine)]"
            />
            <p className="text-xs text-[var(--muted)]">
              Narrows the subject filter used when scanning the corpus. Leave blank to rely on BISAC alone.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="project-freshness" className="text-sm font-medium text-[var(--ink)]">
              Timely &harr; evergreen <span className="text-[var(--muted)]">(default, editable later in Settings)</span>
            </label>
            <input
              id="project-freshness"
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={timelyEvergreen}
              onChange={(e) => setTimelyEvergreen(Number(e.target.value))}
              className="w-full accent-[var(--ultramarine)]"
            />
            <div className="flex justify-between text-xs text-[var(--muted)]">
              <span>Evergreen</span>
              <span>Timely</span>
            </div>
          </div>

          {submitError ? (
            <p className="text-sm text-[var(--oxblood)]">{submitError}</p>
          ) : null}

          <div className="flex items-center justify-end gap-3">
            <Button type="submit" variant="primary" disabled={createProject.isPending}>
              {createProject.isPending ? "Creating…" : "Create project"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
