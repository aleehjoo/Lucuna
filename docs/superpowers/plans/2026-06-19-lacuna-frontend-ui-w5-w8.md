# Lacuna Frontend — UI (W5→W8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **PRECONDITION:** Plan A's **W4 gate (Task 12) must be green** — live search proven on a real title — before starting W6's Search surface (Frontend PRD §16). W5 (skeleton) may begin in parallel with backend hardening, but Search UI waits on the gate.

**Goal:** Build the Next.js product UI over the proven FastAPI backend — project workspaces, live single-title search, niche dashboard, category sweep, operator seed, settings, real data charts — then retire Streamlit, leaving one coherent UI.

**Architecture:** Next.js App Router (TypeScript, Tailwind) talks ONLY to the FastAPI backend (no keys client-side). TanStack Query owns server state and job polling. Every async action is a `jobs`-backed status component. A deliberate, subject-rooted design system (the "lacuna / negative-space" identity) is applied throughout via the frontend-design skill.

**Tech Stack:** Next.js (App Router, TS, Tailwind v4), `@tanstack/react-query`, Recharts, Vitest + React Testing Library (component tests), Playwright (one end-to-end search smoke). Fonts: Fraunces (display), Inter (body/UI), IBM Plex Mono (data/provenance).

## Global Constraints

- **Frontend holds no secrets** (Frontend PRD §13.7/§15): the app calls only `NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`); never an upstream source or key.
- **One UI** (§13.11/§14): Streamlit is retired at the end (W8) after parity; the CLI stays for operators.
- **Two execution models surfaced honestly** (§1.2): Search = live/seconds (inline spinner); Seed = batch/~1h (persistent progress bar, survives navigation). Never imply the corpus runs on a user search.
- **Correctness knobs are NOT in the UI** (§10/§13.10): Settings exposes intent knobs only (timely↔evergreen, recency window, export size/token budget, target BISAC on create). `min_critical_per_work`, shrinkage, epsilon, normalization, revisions stay in `advanced.yaml`.
- **Only visualize data we have** (§7/§12): complaint aspects, rating distribution, cluster composition, demand-vs-supply (proxies, labeled), gap candidates, cross-platform agreement, provenance/coverage. **No price or sales charts.**
- **No dead ends** (§11): every empty/loading/error state names a next action; thin/degenerate data is labeled honestly ("low signal: N reviews, 1 cluster").
- **Use the frontend-design skill for all UI** (§6/§18): apply the design system below; no default-template styling ships.
- **Use Context7 live docs** (§18) for Next.js, TanStack Query, and Recharts before non-trivial calls.
- **Prereqs:** Node ≥ 20 and npm available on PATH. The Next.js app lives in `frontend/` (sibling to `api/` and `lacuna/`). Backend must be running (`.venv\Scripts\uvicorn.exe api.app:create_app --factory --port 8000`) for live verification steps.

---

## Design System (frontend-design skill — plan, then critique)

**Subject pinned:** Lacuna helps an indie author / small publisher find the book that *should* exist but doesn't — by mining where readers complain. The single job of the product surface: turn dissatisfaction signal into a defensible, honestly-caveated hypothesis. A *lacuna* is a gap in a manuscript — that is the thesis the whole identity encodes: **the opportunity is the negative space.**

**Color (6 named values) — "ink & vellum, cold data layer":**
```
--ink:        #16202B   /* deep slate-ink; primary text & strong UI (near-black, blue-cast) */
--paper:      #F5F4EF   /* cool paper; app background (pushed cooler than the #F4F1EA default) */
--panel:      #FFFFFF   /* cards/surfaces */
--ultramarine:#27408B   /* primary action / links / focus — the analytical layer */
--gold-leaf:  #B8860B   /* THE GAP / opportunity — illuminated-manuscript gold (not terracotta) */
--oxblood:    #8C2F2A   /* dissatisfaction / complaint intensity & destructive actions */
```
Neutrals derive from `--ink` at reduced alpha (borders `--ink/12`, muted text `--ink/55`).

**Type (3 roles):**
- Display: **Fraunces** (variable, optical serif — bookish character, used with restraint on hero + page titles only). Deliberately *not* Playfair (default #1's high-contrast serif).
- Body/UI: **Inter** — legibility for a console-grade tool; defensible because this is a workbench, not a magazine.
- Data/utility: **IBM Plex Mono** — BISAC codes, sample sizes, provenance chips, gap scores. The "evidence" layer reads as technical.

**Layout:** GCP-console shell — persistent top bar (project switcher + health/“warming up” indicator), left nav (Search · Niche Dashboard · Category Sweep · Seed & Data · Settings), content canvas on `--paper`.

**Signature — the Gap Strip:** candidates are rendered as horizontal bars where the **unfilled** portion (rendered in `--gold-leaf` as a void, not a fill) is visually dominant — inverting the usual "filled = good." The larger the gap_score, the more gold void. This makes "underserved = empty space" a structural truth, not decoration. The empty/onboarding states reuse the motif: a manuscript line with a blanked slot where the missing title would sit.

**Self-critique (revise against defaults):** Working the generic prompt "dashboard for a book-analytics tool" lands on cream+serif (#1) or a Linear-style dark console (#2). This direction diverges deliberately: cool paper (not warm cream), gold-leaf-as-void as the memorable element (not a terracotta accent), and the negative-space inversion is specific to *this* product's thesis rather than a reusable template. Boldness is spent in one place (the Gap Strip); everything else stays quiet — hairline `--ink/12` borders, generous spacing, mono only for data. Quality floor (non-negotiable): responsive to mobile, visible keyboard focus (`--ultramarine` ring), `prefers-reduced-motion` respected.

---

## File Structure (`frontend/`)

- `frontend/` — Next.js app (App Router, `src/` dir, import alias `@/*`).
- `src/app/layout.tsx` — root layout: fonts, `<Providers>`, app shell.
- `src/app/globals.css` — design tokens + base styles.
- `src/app/providers.tsx` — `QueryClientProvider` (client component).
- `src/app/(workspace)/projects/page.tsx` — Projects home (landing).
- `src/app/(workspace)/projects/new/page.tsx` — New Project.
- `src/app/(workspace)/p/[projectId]/search/page.tsx` — Search.
- `src/app/(workspace)/p/[projectId]/dashboard/page.tsx` — Niche Dashboard.
- `src/app/(workspace)/p/[projectId]/sweep/page.tsx` — Category Sweep.
- `src/app/(workspace)/p/[projectId]/seed/page.tsx` — Seed & Data.
- `src/app/(workspace)/p/[projectId]/settings/page.tsx` — Settings.
- `src/lib/api.ts` — typed fetch client (the only thing that talks to the backend).
- `src/lib/types.ts` — DTO types mirroring `api/schemas.py`.
- `src/lib/hooks.ts` — TanStack Query hooks (`useProjects`, `useJob`, `useStartSearch`, …).
- `src/components/shell/TopBar.tsx`, `ProjectSwitcher.tsx`, `LeftNav.tsx`.
- `src/components/ui/Button.tsx`, `Card.tsx`, `Chip.tsx`, `FlagBadge.tsx`, `EmptyState.tsx`, `Skeleton.tsx`, `ErrorState.tsx`.
- `src/components/JobStatus.tsx` — polling status (core).
- `src/components/charts/GapStrip.tsx` (signature), `AspectFrequency.tsx`, `RatingHistogram.tsx`, `DemandSupply.tsx`, `AgreementGauge.tsx`, `ProvenanceChips.tsx`.
- Tests: `src/**/*.test.tsx` (Vitest), `e2e/search.spec.ts` (Playwright).

---

## W5 — Frontend Skeleton

### Task 1: Scaffold the Next.js app

**Files:** Create `frontend/` via the scaffolder; add `frontend/.env.local`.

- [ ] **Step 1: Pull current scaffolding docs** (Context7, per §18)

Query `/vercel/next.js` for "create-next-app non-interactive flags App Router TypeScript Tailwind src-dir import-alias" before running, to match the current CLI.

- [ ] **Step 2: Scaffold (non-interactive)**

```bash
cd C:/Users/Alejandro/Documents/Lacuna
npx create-next-app@latest frontend --ts --tailwind --app --src-dir --import-alias "@/*" --eslint --use-npm --no-turbopack
```
Expected: `frontend/` created with `src/app/`, Tailwind wired, `tsconfig.json` with `@/*`.

- [ ] **Step 3: Add the API base env + deps**

`frontend/.env.local`:
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```
Install runtime deps:
```bash
cd C:/Users/Alejandro/Documents/Lacuna/frontend
npm install @tanstack/react-query recharts
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react @playwright/test
```

- [ ] **Step 4: Verify it builds**

Run: `npm run build`
Expected: build succeeds (default scaffold).

- [ ] **Step 5: Commit**

```bash
git add frontend/ .gitignore
git commit -m "chore(frontend): scaffold Next.js App Router (TS+Tailwind) + deps"
```
> Confirm `frontend/.env.local` and `frontend/node_modules` are gitignored (extend root `.gitignore` if needed — `CLAUDE.md` §5).

---

### Task 2: Design tokens + base UI primitives

**Files:** Modify `src/app/globals.css`, `src/app/layout.tsx`; create `src/components/ui/{Button,Card,Chip,FlagBadge,EmptyState,Skeleton,ErrorState}.tsx`.

**Interfaces:**
- Produces: CSS variables (the 6 colors + font vars); `<Button variant="primary|ghost|danger">`, `<Card>`, `<Chip mono>`, `<FlagBadge flag="incomplete|blind_spot|recent_supply_surge|low_signal">`, `<EmptyState title action>`, `<Skeleton>`, `<ErrorState message onRetry>`.

- [ ] **Step 1: Write tokens into `globals.css`**

Replace the scaffold's `globals.css` body with the token layer (keep Tailwind's `@import`):

```css
@import "tailwindcss";

:root {
  --ink: #16202B;
  --paper: #F5F4EF;
  --panel: #FFFFFF;
  --ultramarine: #27408B;
  --gold-leaf: #B8860B;
  --oxblood: #8C2F2A;
  --border: color-mix(in srgb, var(--ink) 12%, transparent);
  --muted: color-mix(in srgb, var(--ink) 55%, transparent);
}

body {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-inter), system-ui, sans-serif;
}
h1, h2, .display { font-family: var(--font-fraunces), Georgia, serif; }
.mono, .data { font-family: var(--font-plex-mono), ui-monospace, monospace; }

*:focus-visible { outline: 2px solid var(--ultramarine); outline-offset: 2px; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

- [ ] **Step 2: Wire fonts in `layout.tsx`**

Use `next/font/google` for Fraunces, Inter, IBM Plex Mono; expose as CSS vars `--font-fraunces`, `--font-inter`, `--font-plex-mono` on `<body>`. (Query Context7 `/vercel/next.js` "next/font/google multiple fonts CSS variable" if the API is unfamiliar.)

- [ ] **Step 3: Build the primitives**

Implement each `ui/*` component as a small typed client/server component using the tokens. Example `Button.tsx`:

```tsx
// src/components/ui/Button.tsx
import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "danger";
const styles: Record<Variant, string> = {
  primary: "bg-[var(--ultramarine)] text-white hover:opacity-90",
  ghost: "bg-transparent text-[var(--ink)] border border-[var(--border)] hover:bg-[color-mix(in_srgb,var(--ink)_5%,transparent)]",
  danger: "bg-[var(--oxblood)] text-white hover:opacity-90",
};

export function Button({ variant = "primary", className = "", ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${styles[variant]} ${className}`}
      {...rest}
    />
  );
}
```

`FlagBadge.tsx` maps each validity flag to a label + color (`incomplete`/`blind_spot` → muted; `recent_supply_surge` → `--oxblood`; `low_signal` → `--oxblood` outline) and a plain-language tooltip carrying the §11 honesty framing.

- [ ] **Step 4: Add a component test**

`src/components/ui/Button.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders danger variant with oxblood background class", () => {
    render(<Button variant="danger">Delete</Button>);
    const btn = screen.getByRole("button", { name: "Delete" });
    expect(btn.className).toContain("--oxblood");
  });
});
```

Add `vitest.config.ts` (jsdom env, `@vitejs/plugin-react`) and a `"test": "vitest run"` script.

- [ ] **Step 5: Run tests + typecheck**

Run: `npm run test` and `npx tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): design tokens + base UI primitives (lacuna identity)"
```

---

### Task 3: API client + types + TanStack Query provider

**Files:** Create `src/lib/{api,types,hooks}.ts`, `src/app/providers.tsx`; modify `layout.tsx`.

**Interfaces:**
- Produces: `api.get/post/del<T>(path)`; types mirroring `api/schemas.py` (`Project`, `JobOut`, `SearchResult`, `Candidate`, …); hooks `useProjects()`, `useProject(id)`, `useJob(jobId, {enabled})`, `useStartSearch(projectId)`, `useStartSeed(projectId)`, `useCandidates(id)`, `useWorks(id)`.

- [ ] **Step 1: Pull TanStack Query App Router setup** (Context7)

Query `/tanstack/query` for "QueryClientProvider in Next.js App Router client component, useQuery refetchInterval polling, useMutation".

- [ ] **Step 2: Implement the client + types**

`src/lib/api.ts`:

```ts
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  get: <T>(p: string) => req<T>(p),
  post: <T>(p: string, body?: unknown) => req<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) }),
  del: <T>(p: string) => req<T>(p, { method: "DELETE" }),
};
```

`src/lib/types.ts` mirrors the DTOs (`ProjectOut`, `JobOut`, candidate/cluster shapes from `reads.py` + `live_single_title` result `counts`).

- [ ] **Step 3: Providers + hooks**

`src/app/providers.tsx` (`"use client"`): create one `QueryClient`, wrap children in `QueryClientProvider`. Mount `<Providers>` in `layout.tsx`.

`src/lib/hooks.ts` — the polling hook is the crux (stop when job terminal):

```ts
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { JobOut, ProjectOut } from "./types";

export const useProjects = () =>
  useQuery({ queryKey: ["projects"], queryFn: () => api.get<ProjectOut[]>("/projects") });

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    enabled: !!jobId,
    queryFn: () => api.get<JobOut>(`/jobs/${jobId}`),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "done" || s === "error" ? false : 1500; // stop polling when terminal
    },
  });
}

export function useStartSearch(projectId: string) {
  return useMutation({
    mutationFn: (body: { title?: string; isbn?: string }) =>
      api.post<{ job_id: string }>(`/projects/${projectId}/search`, body),
  });
}

export function useStartSeed(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { meta_limit: number; review_limit: number; max_works: number }) =>
      api.post<{ job_id: string }>(`/projects/${projectId}/seed`, body),
    onSettled: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}
```

- [ ] **Step 4: Test the polling stop condition**

`src/lib/hooks.test.tsx` — render `useJob` via a Testing Library wrapper with a mocked `api.get` returning `{status:"done"}`; assert `refetchInterval` resolves to `false`. (Unit-test the interval function directly if simpler: export it and assert `intervalFn({state:{data:{status:"done"}}}) === false`.)

- [ ] **Step 5: Run tests + typecheck**

Run: `npm run test && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): API client, DTO types, TanStack Query provider + job polling hook"
```

---

### Task 4: App shell — top bar, project switcher, left nav

**Files:** Create `src/components/shell/{TopBar,ProjectSwitcher,LeftNav}.tsx`; modify `layout.tsx` and add the `(workspace)` route group layout `src/app/(workspace)/layout.tsx`.

**Interfaces:**
- Produces: persistent top bar with `<ProjectSwitcher>` (lists projects via `useProjects`, routes to `/p/[id]/dashboard`) and a backend-health indicator (`GET /health` → "warming up the analysis engine" when `models_ready` is false, §8); `<LeftNav>` with the five sections, active-state aware.

- [ ] **Step 1: Build the shell**

`(workspace)/layout.tsx` composes `<TopBar />` + `<LeftNav />` + `{children}` on `--paper`. `ProjectSwitcher` is a `"use client"` dropdown (GCP-style) reading `useProjects()`; selecting navigates with `next/navigation` `useRouter`. Health indicator polls `/health` every 5s until ready, then stops.

- [ ] **Step 2: Health-indicator test**

`src/components/shell/TopBar.test.tsx` — mock `/health` returning `{models_ready:false}` → assert "warming up" copy renders; `{models_ready:true}` → indicator shows ready.

- [ ] **Step 3: Verify build + visual critique**

Run: `npm run build && npx tsc --noEmit`. Start `npm run dev`, open `http://localhost:3000` (backend running). **Design critique (skill):** screenshot the shell; confirm the identity reads (Fraunces titles, cool paper, ultramarine focus rings), not a default template. Remove one accessory if it feels busy.

- [ ] **Step 4: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): app shell — top bar, project switcher, left nav, health indicator"
```

---

### Task 5: `JobStatus` component (the core async UX)

**Files:** Create `src/components/JobStatus.tsx`; test `src/components/JobStatus.test.tsx`.

**Interfaces:**
- Consumes: `useJob(jobId)`.
- Produces: `<JobStatus jobId onDone={(job)=>...} variant="bar|inline" />` — renders queued→running (progress bar + `step`)→done (calls `onDone`)→error (message + retry). `variant="bar"` for seed (%/step), `"inline"` spinner for search.

- [ ] **Step 1: Write the failing test**

```tsx
// src/components/JobStatus.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
// mock useJob to return a running then done state; assert progress + onDone fires.
```
Assert: running → shows `step` text and an accessible progressbar with `aria-valuenow`; error → shows `error_detail` + a "Try again" button; done → `onDone` called once.

- [ ] **Step 2: Implement**, run `npm run test` + `tsc --noEmit` → PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/JobStatus.tsx frontend/src/components/JobStatus.test.tsx
git commit -m "feat(frontend): JobStatus polling component (queued/running/done/error)"
```

---

## W6 — Surfaces

> Search (Task 8) requires the W4 gate green. Others depend only on read endpoints.

### Task 6: Projects home + onboarding empty state

**Files:** `src/app/(workspace)/projects/page.tsx`, `src/components/ProjectCard.tsx`.

- [ ] **Step 1:** Grid of `<ProjectCard>` (name, niche/BISAC mono chips, seeded status, work/cluster counts, last activity) from `useProjects()`. "New Project" CTA → `/projects/new`.
- [ ] **Step 2:** First-run empty state (no projects) → guided "Create your first project" using the manuscript-blank signature motif; the empty state names the action (§11).
- [ ] **Step 3:** Loading → `<Skeleton>` cards; error → `<ErrorState onRetry>`.
- [ ] **Step 4:** Component test: renders cards for a mocked project list; renders onboarding when list empty.
- [ ] **Step 5:** Build + typecheck + visual critique. Commit `feat(frontend): projects home + onboarding empty state`.

### Task 7: New Project form

**Files:** `src/app/(workspace)/projects/new/page.tsx`.

- [ ] **Step 1:** Form (name; target BISAC picker over validated codes; keywords; intent-config defaults). Submitting calls `POST /projects` via a mutation; on success route to the new project's dashboard. **Creating does not auto-seed** (§6.2) — copy says so.
- [ ] **Step 2:** Validation: name required, ≥1 BISAC. Inline errors in interface voice (§ writing).
- [ ] **Step 3:** Test: submits valid payload → mutation called with the right body; blocks empty name.
- [ ] **Step 4:** Build + typecheck. Commit `feat(frontend): new project form`.

### Task 8: Search surface (live single-title) — **gate-dependent**

**Files:** `src/app/(workspace)/p/[projectId]/search/page.tsx`, `src/components/SearchResult.tsx`.

- [ ] **Step 1: Confirm the W4 gate is green** (Plan A Task 12). If not, stop.
- [ ] **Step 2:** Prominent search box ("Search a book title or ISBN"). Submit → `useStartSearch` → `<JobStatus variant="inline" jobId onDone={setResult}>`.
- [ ] **Step 3:** `<SearchResult>` renders from `job.counts`: clustered complaints (paraphrased), rating summary, demand/supply signals, provenance line, validity flags, charts (wired in W7), and a Context Pack download (`GET /export`). Clearly indicate **historical+fresh vs fresh-only** ("no historical depth — live Hardcover only") per `fresh_only`.
- [ ] **Step 4:** Thin-data honesty (§11): if `review_count` small or one cluster, show "low signal: N reviews, 1 cluster — interpret cautiously" via `<FlagBadge flag="low_signal">`.
- [ ] **Step 5:** Test: mocked search mutation + job done with a fresh-only payload → asserts the fresh-only notice and complaint list render.
- [ ] **Step 6:** Live verify (backend + gate green): search "Atomic Habits" in the UI → result returns in seconds, fresh-only flagged. Build + typecheck. Commit `feat(frontend): live single-title search surface`.

### Task 9: Niche Dashboard

**Files:** `src/app/(workspace)/p/[projectId]/dashboard/page.tsx`.

- [ ] **Step 1:** Browse seeded project: top works (`/works`), niche-level complaint clusters (`/clusters?scope=bisac`), gap candidates (`/candidates`), summary KPIs. Charts wired in W7.
- [ ] **Step 2:** Empty state if not seeded: "Seed this niche to unlock historical depth — or search any title live" with links to Seed & Data and Search (§6.4, no dead end).
- [ ] **Step 3:** Test: renders works + clusters from mocks; renders empty state when `seeded:false`.
- [ ] **Step 4:** Build + typecheck + visual critique. Commit `feat(frontend): niche dashboard`.

### Task 10: Category Sweep

**Files:** `src/app/(workspace)/p/[projectId]/sweep/page.tsx`.

- [ ] **Step 1:** Ranked BISAC gap candidates (`/candidates`, bisac scope), each expandable with flags, sample size, platforms, and a Context Pack export (`/export?scope=category_sweep`). Advanced-mode banner (§6.5).
- [ ] **Step 2:** Uses the **Gap Strip** (signature) for the ranked list (W7 Task 13).
- [ ] **Step 3:** Test: renders ranked candidates desc by gap_score; expand reveals flags + provenance.
- [ ] **Step 4:** Build + typecheck. Commit `feat(frontend): category sweep surface`.

### Task 11: Seed & Data (operator)

**Files:** `src/app/(workspace)/p/[projectId]/seed/page.tsx`.

- [ ] **Step 1:** Trigger a seed (inputs: meta_limit, review_limit, max_works) → `useStartSeed` → `<JobStatus variant="bar">` showing %/step from the `jobs` row. History of past seed jobs (`/projects/{id}/jobs`, kind=seed). Honest time estimate + a "this is a long operation (~1 hour); you can navigate away" warning (§6.6/§8).
- [ ] **Step 2:** The progress bar must survive navigation: state lives in the job, re-polled on return (TanStack Query cache keyed by job id). Verify by navigating away and back during a (mocked) running job.
- [ ] **Step 3:** Test: start-seed mutation called with inputs; running job renders %/step bar; past-jobs list renders.
- [ ] **Step 4:** Build + typecheck. Commit `feat(frontend): seed & data operator surface`.

### Task 12: Settings (intent knobs only)

**Files:** `src/app/(workspace)/p/[projectId]/settings/page.tsx`.

- [ ] **Step 1:** Expose ONLY intent knobs (§10/§13.10): timely↔evergreen slider, recency window, export max candidates + token budget. Persist into the project's `config` (PATCH/PUT project — add `PUT /projects/{id}` to Plan A if not present, or store via `POST` config field; flag this dependency).
- [ ] **Step 2:** Assert (in code + a test) that correctness knobs (`min_critical_per_work`, shrinkage, epsilon, normalization, revisions) are absent from the UI — a guard test that the settings schema contains none of those keys (§13.10, acceptance §9).
- [ ] **Step 3:** Build + typecheck. Commit `feat(frontend): settings — intent knobs only`.

---

## W7 — Visualizations (Recharts; only data we have)

### Task 13: Chart primitives + wiring

**Files:** `src/components/charts/{GapStrip,AspectFrequency,RatingHistogram,DemandSupply,AgreementGauge,ProvenanceChips}.tsx`; wire into dashboard/search/sweep.

- [ ] **Step 1: Pull Recharts docs** (Context7) — query `/recharts/recharts` for "ResponsiveContainer BarChart horizontal layout, histogram, Cell per-bar color, custom tooltip".
- [ ] **Step 2: GapStrip (signature).** Horizontal bar per candidate; total width = max gap. Render the **gap** (`gap_score`) as a `--gold-leaf` void segment and the "filled/served" remainder muted — inverting fill semantics. Confidence drives opacity; flag badges inline. Each bar shows its provenance (n, platforms) in mono. Example skeleton:

```tsx
"use client";
import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { Candidate } from "@/lib/types";

export function GapStrip({ candidates }: { candidates: Candidate[] }) {
  const data = candidates.map((c) => ({ name: c.title, gap: c.gap_score, conf: c.confidence }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 44)}>
      <BarChart data={data} layout="vertical" margin={{ left: 16, right: 24 }}>
        <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => v.toFixed(1)} />
        <YAxis type="category" dataKey="name" width={220} tick={{ fontSize: 12 }} />
        <Tooltip formatter={(v: number) => v.toFixed(2)} />
        <Bar dataKey="gap" radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {data.map((d, i) => (
            <Cell key={i} fill="var(--gold-leaf)" fillOpacity={0.35 + 0.65 * d.conf} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 3: The rest:** `AspectFrequency` (bar of clustered aspects by reviewer_count — the core "what readers complain about" view); `RatingHistogram` (per-work rating distribution); `DemandSupply` (paired bars per BISAC candidate, demand proxy vs supply scarcity — **labeled "popularity proxy, not sales"** §7/§12); `AgreementGauge` (cross-platform agreement %); `ProvenanceChips` (sample-size + date-range chips, mono, with the timely↔evergreen freshness dimming). **No price/sales charts.**
- [ ] **Step 4:** Each chart shows provenance and never implies more certainty than the sample supports (§7). Add a `reduced-motion` guard (`isAnimationActive={false}` when preferred).
- [ ] **Step 5:** Tests: GapStrip renders one bar per candidate; DemandSupply renders the "proxy" label; charts render an empty/"no data" state, never a blank box.
- [ ] **Step 6:** Wire charts into Search result, Niche Dashboard, Category Sweep. Build + typecheck + visual critique (screenshot the GapStrip — confirm the gold-void inversion reads as the memorable element). Commit `feat(frontend): data visualizations (gap strip signature + §7 charts)`.

---

## W8 — Polish & Retire

### Task 14: Honesty framing, graceful degradation, cancellation

**Files:** cross-cutting — `SearchResult`, dashboard, `JobStatus`, a shared `<HypothesisBanner>`.

- [ ] **Step 1:** Every analysis result restates "treat as a hypothesis, not a finding" (§11) via `<HypothesisBanner>`, carrying the Context Pack posture into the UI.
- [ ] **Step 2:** Graceful degradation (§11): Hardcover down → show historical-only with a notice; corpus not seeded → fresh-only. Map backend 503 (`HARDCOVER_API_TOKEN` not configured) to a clear, non-alarming message.
- [ ] **Step 3:** Cancellation (§11): allow cancelling a running live-search job. Add `POST /jobs/{id}/cancel` to Plan A (sets `status='error'`/`'cancelled'`) — **flag this backend dependency**; the UI calls it and stops polling.
- [ ] **Step 4:** Audit every empty/error state for a next action; no dead ends (§11, acceptance §8).
- [ ] **Step 5:** Tests for degradation copy + cancel flow (mocked). Build + typecheck. Commit `feat(frontend): honesty framing, graceful degradation, cancellation`.

### Task 15: Retire Streamlit + docs

**Files:** Delete `app/streamlit_app.py` and its tests; update `README` / `docs`.

- [ ] **Step 1: Confirm parity first** (§14): the Next.js app covers browse + search + sweep + seed-trigger. Walk each Streamlit feature and confirm a Next.js equivalent exists. **Do NOT delete before parity is confirmed** (`CLAUDE.md` §2).
- [ ] **Step 2:** Find Streamlit references:

Run: `.venv\Scripts\python.exe -c "print('search streamlit refs')"` then use Grep for `streamlit` across the repo (config, docs, pyproject `streamlit>=1.36`, tests). List every hit before removing.

- [ ] **Step 3:** Remove `app/streamlit_app.py` and any streamlit-only test. Decide on the `streamlit` dependency: drop it from `pyproject.toml` only if nothing else imports it (confirm via Grep). The CLI stays (§14).
- [ ] **Step 4:** Update docs: README documents `uvicorn api.app:create_app --factory` + `cd frontend && npm run dev`, the two-actor/two-execution model, and that the CLI remains for operators. Note the W4 gate in METHODOLOGY.
- [ ] **Step 5: Verify the suite still passes** (`superpowers:verification-before-completion`):

Run: `.venv\Scripts\pytest.exe -q`
Expected: PASS (no orphaned streamlit-test imports). Then `cd frontend && npm run build && npm run test`.

- [ ] **Step 6:** Commit `chore: retire Streamlit (Next.js is the one UI); docs for FastAPI+Next.js stack`.

---

## End-to-End Acceptance (Frontend PRD §17) — run before declaring done

- [ ] Playwright smoke `e2e/search.spec.ts`: with backend running + gate green, search a never-seeded title → live result with provenance in seconds (§17.2/§17.4).
- [ ] Two projects coexist with isolated dashboards (§17.6) — manual.
- [ ] Charts render real data with provenance; no price/sales charts (§17.7) — visual audit.
- [ ] Every async action shows queued→running→done/error; no blank panels (§17.8) — audit.
- [ ] Correctness knobs absent from UI (§17.9) — Task 12 guard test.
- [ ] Streamlit removed, CLI works, one UI (§17.10) — Task 15.

## Self-Review (against Frontend PRD §6/§7/§8/§16)

- **§6 surfaces:** projects home (T6), new project (T7), search (T8), niche dashboard (T9), sweep (T10), seed & data (T11), settings (T12). ✅
- **§7 charts:** all seven buildable charts (T13); no price/sales. ✅
- **§8 job UX:** JobStatus (T5) used by search (inline) + seed (bar); model warm-up indicator (T4); skeletons/empty/error in each surface. ✅
- **§16 gate:** Search (T8) explicitly blocked on Plan A's W4 gate. ✅
- **Backend dependencies surfaced (flag per `CLAUDE.md` §2):** Settings needs `PUT /projects/{id}` (T12); cancellation needs `POST /jobs/{id}/cancel` (T14). Both are small additions to Plan A — call them out before W8 so they're built, not improvised.
- **Frontend testing note:** UI uses build + typecheck + Vitest component tests + one Playwright smoke instead of strict red-green TDD per micro-step (the writing-plans TDD cycle is adapted for UI, which the skill permits for flexible work). Logic-bearing units (the polling interval, settings-knob guard) DO get unit tests.

---

*Frontend done when §17 acceptance passes and Streamlit is retired, leaving one coherent UI over the proven engine.*
