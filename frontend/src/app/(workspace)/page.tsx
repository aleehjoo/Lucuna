import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { FlagBadge } from "@/components/ui/FlagBadge";

// This is a SKELETON / preview landing (app shell, Plan B Task 4) — not the
// real Projects home (that surface is built in W6). Its only job here is to
// let a human judge the identity: Fraunces display type, cool paper canvas,
// ultramarine accents, mono for evidence/data, and the honesty framing
// (flags that say what's missing rather than hiding it).
export default function Home() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-10 py-6">
      <section className="flex flex-col gap-3">
        <h1 className="display text-5xl leading-tight text-[var(--ink)]">
          Find the book that should exist but doesn&apos;t.
        </h1>
        <p className="max-w-xl text-base text-[var(--muted)]">
          Lacuna reads what readers already complained about — across
          platforms — and scores the gap between demand and supply. No
          guessing, no inflated confidence: every number ships with its
          receipts.
        </p>
      </section>

      <Card className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Chip mono>BISAC FIC044000</Chip>
            <span className="text-sm text-[var(--muted)]">
              Stoicism &amp; Philosophy &mdash; sample candidate
            </span>
          </div>
          <div className="flex gap-2">
            <FlagBadge flag="fresh_only" />
            <FlagBadge flag="low_signal" />
          </div>
        </div>

        <p className="text-sm text-[var(--ink)]">
          A gap score is only as good as what we admit we don&apos;t know yet.
          <span className="text-[var(--muted)]">
            {" "}
            These flags travel with every candidate — hover one for the plain-
            language reason.
          </span>
        </p>

        <div className="flex flex-wrap gap-3">
          <Button variant="primary">Create a niche</Button>
          <Button variant="ghost">View sample export</Button>
          <Button variant="danger">Discard project</Button>
        </div>
      </Card>

      <EmptyState
        title="No projects yet"
        description="Create your first niche to seed a corpus, run the local NLP pipeline, and surface the gaps no one else is scoring."
        action={<Button variant="primary">Create your first niche</Button>}
      />
    </div>
  );
}
