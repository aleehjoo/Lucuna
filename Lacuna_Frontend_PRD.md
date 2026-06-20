# Lacuna — Frontend Product PRD (Path B: Full Application)

**Version:** 1.0 — execution-ready
**Build agent:** Claude Code
**Status of the engine:** BUILT. This PRD adds a real product surface on top of the existing Python engine. It does **not** rebuild the engine.
**Prime directive:** Wrap and reuse the existing `lacuna` Python package behind an API. Do not reimplement adapters, NLP, scoring, or export. If a behavior is missing, add a thin new layer that *calls* the existing engine.

---

## 0. Context — What Exists vs. What This Adds

**Already built (reuse, do not touch the internals):**
- The `lacuna` Python package: adapters (Hardcover, Google Books, NYT, Open Library, Amazon corpus), local NLP (embeddings + HDBSCAN + zero-shot labeling), demand-gated resilient scoring, Context Pack export, the batch seed pipeline, the Typer CLI.
- Supabase schema with full `project_id` isolation (projects, works, editions, reviews, aspect_clusters, demand_signals, supply_signals, scores, taxonomy_crosswalk, unmapped_labels, analysis_runs).
- A working (but bare) Streamlit dashboard — to be retired (see §14).

**What this PRD adds:**
- A **FastAPI backend** that wraps the engine as a REST API.
- A **Next.js frontend** — the real product UI.
- A **live, on-demand single-title analysis path** (new engine glue — Hardcover-driven, runs in seconds).
- A **job/progress system** so both the long batch seed and the fast live search report status to the UI.
- Real **data visualizations**, **project/workspace management**, and **loading/empty/error UX**.

---

## 1. The Product Model — the central concept, read this first

Lacuna has **two kinds of actor** and **two kinds of execution**. Conflating them is the #1 source of downstream bugs, so they are defined explicitly.

### 1.1 Two actors
- **Operator** (you, or whoever runs an instance): creates projects (niches), runs the slow batch corpus seed, manages config. Power actions.
- **User** (anyone using a seeded instance): searches a title, browses a seeded niche, runs a category sweep, downloads the Context Pack. Fast actions.

### 1.2 Two execution models — **these must never be merged**
| | **Batch Seed** (historical/corpus) | **Live Search** (fresh/Hardcover) |
|---|---|---|
| Trigger | Operator runs a seed for a project | User searches a title |
| Source | McAuley Amazon corpus (571M rows, streamed) | Hardcover API (a few calls) |
| Duration | ~1 hour | seconds |
| Where it runs | Background subprocess (CPU-heavy, batch) | API request → job (CPU in a worker pool) |
| Output | Pre-computed works/clusters/scores for the niche | On-demand clusters/scores for one title |

**HARD RULE:** The corpus is **never** queried live in response to a user search. It is too large (hour-scale). Only the **Hardcover** layer runs on demand. Any design that makes a user wait on a corpus scan is wrong.

### 1.3 The hybrid that makes it one product
When a user searches a title:
1. **Seeded lookup (instant):** check whether the title already exists in the project's seeded corpus data. If yes, its historical clusters/scores load immediately.
2. **Live pull (seconds):** run a live Hardcover analysis for that title (fresh reviews → embed/cluster/score).
3. **Merge:** combine the two layers with provenance, per the existing cross-platform aggregation (`aggregation/cross_platform.py`). Cross-source agreement raises confidence.
4. **Not-seeded case:** if the title isn't in any seed, the user still gets a **fresh-only** result, clearly flagged "no historical depth — live Hardcover only."

So the product is **both** a browsable pre-seeded niche dashboard **and** a live single-title search — and a title needs no prior seeding to be searchable.

### 1.4 Note on "data day one" (clears the earlier confusion)
Pre-seeded data is **not** a product requirement. A user can search a brand-new title and get a live result with zero prior seeding. Seeded data exists so that (a) niche browsing/sweeps have depth, and (b) **during development**, the UI can be built and verified against real rows. The latter is dev scaffolding, not product behavior — do not design the UI to *require* a seed before it functions.

---

## 2. System Architecture

```
┌─────────────────┐     HTTP/JSON      ┌──────────────────────┐
│  Next.js (3000) │ ◄────────────────► │  FastAPI (8000)      │
│  - UI surfaces  │   (CORS, no keys   │  - wraps lacuna pkg  │
│  - charts       │    on frontend)    │  - warm NLP models   │
│  - job polling  │                    │  - job orchestration │
└─────────────────┘                    └──────────┬───────────┘
                                                   │ imports/calls
                              ┌────────────────────┴───────────────────┐
                              │  existing `lacuna` package (UNCHANGED   │
                              │  internals): adapters, nlp, scoring,    │
                              │  export, seed pipeline                  │
                              └────────────────────┬───────────────────┘
                                                   │
                                          ┌────────┴────────┐
                                          │ Supabase (PG +  │
                                          │ pgvector)       │
                                          └─────────────────┘
   Batch seed runs as a SEPARATE SUBPROCESS (existing CLI) → writes progress to `jobs` table.
```

- **Frontend never holds API keys.** All engine/source calls go through the backend. The frontend only ever talks to the FastAPI backend.
- **Backend reuses the engine by import**, not reimplementation.
- **Models load once at backend startup** and stay warm in memory (the ~1.6 GB zero-shot model + the embedding model). Live search must not reload them per request.
- **Heavy CPU (embed/cluster) runs in a worker pool** (ProcessPool/thread pool), never on the API event loop.
- **The batch seed runs as a subprocess** of the existing CLI (it's CPU-heavy and hour-long); it reports progress into the `jobs` table.

---

## 3. The Two Execution Models — Detailed

### 3.1 Batch Seed (operator, slow, corpus)
- Triggered from the UI (operator) → backend creates a `jobs` row (`kind='seed'`, `status='queued'`) → launches the existing `lacuna seed` CLI as a subprocess scoped to the project.
- The seed writes progress to the `jobs` row (extend the existing progress logging with a jobs-table callback: `progress_pct`, `step`, `counts`).
- Not resumable (matches current reality): a crash → job `status='error'`; operator re-runs. Document this; do not fake resumability.
- On success → job `status='done'`; the project's works/clusters/scores are now populated.

### 3.2 Live Single-Title Search (user, fast, Hardcover) — NEW engine glue
A new orchestrator (`lacuna/pipeline/live_single_title.py`) that **reuses existing components**:
1. **Resolve title** → query Hardcover search (existing adapter) for the best-match book; also look up any seeded work with a matching normalized key in the current project.
2. **Live pull** → fetch the title's Hardcover reviews (existing adapter, `user_books` path).
3. **Local NLP** → embed + cluster those reviews using the **warm** models (existing `nlp/` functions) in a worker pool.
4. **Merge** → if a seeded corpus work exists, merge live + historical clusters via existing `aggregation/cross_platform.py`; else fresh-only.
5. **Score + export** → existing scoring + Context Pack.
- Wrapped as a `jobs` row (`kind='live_search'`) so the UI gets consistent progress UX even though it's seconds, and so a slow Hardcover call doesn't hang a request.

### 3.3 Merge & provenance rules (reuse existing semantics)
- Per-platform normalization before combining (existing).
- Cross-platform agreement raises confidence (existing).
- Every surfaced result carries provenance: platforms used, review count, date ranges, confidence, and the validity flags (`incomplete`, `blind_spot`, `recent_supply_surge`).
- Fresh-only results are flagged "no historical depth."

---

## 4. Backend API (FastAPI)

Endpoints (all JSON; all engine work delegated to the `lacuna` package):

**Projects**
- `GET /projects` — list (id, name, target_bisac, seeded?, counts, last_seed_at)
- `POST /projects` — create (name, target_bisac, subject_filter, config)
- `GET /projects/{id}` — detail + summary stats
- `DELETE /projects/{id}` — delete (cascade)

**Seed (operator)**
- `POST /projects/{id}/seed` — start a batch seed job (params: meta_limit, review_limit, max_works) → returns job id
- (status via `GET /jobs/{id}`)

**Live search (user)**
- `POST /projects/{id}/search` — body `{title or isbn}` → starts a `live_search` job → returns job id
- `GET /projects/{id}/works?query=` — exact/prefix match over seeded works (powers search + optional autocomplete later)

**Category sweep**
- `POST /projects/{id}/sweep` — start a sweep job → job id
- `GET /projects/{id}/candidates` — ranked BISAC candidates with scores + flags

**Reads for the dashboard**
- `GET /projects/{id}/works/{workId}` — work detail: ratings, editions, clusters, provenance
- `GET /projects/{id}/clusters?scope=work|bisac&ref=...`
- `GET /projects/{id}/scores`

**Export**
- `GET /projects/{id}/export?scope=...&ref=...&format=json|md` — Context Pack (existing exporter)

**Jobs**
- `GET /jobs/{id}` — `{status, kind, progress_pct, step, counts, result_ref, error}`
- `GET /projects/{id}/jobs` — recent jobs for the project

**Infra**
- CORS allowing `localhost:3000`.
- Models loaded at startup (lifespan handler) into a singleton; a `/health` endpoint reports model-ready state so the UI can show "warming up."
- All secrets read server-side from `.env` (existing config layer). Never returned to the client.

---

## 5. Database Additions

Reuse the entire existing schema. Add one table (alembic migration):

```sql
create table jobs (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid references projects(id) on delete cascade,
  kind         text not null check (kind in ('seed','live_search','sweep')),
  status       text not null default 'queued' check (status in ('queued','running','done','error')),
  progress_pct numeric(5,2) not null default 0,
  step         text,
  counts       jsonb,
  result_ref   text,            -- e.g. work_id or candidate id to load on completion
  error_detail text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index jobs_project_idx on jobs (project_id, created_at desc);
```
No other schema changes. The existing `analysis_runs` stays for engine-level observability; `jobs` is the UI-facing status surface.

---

## 6. Frontend (Next.js) — Surfaces

App Router, TypeScript, Tailwind, TanStack Query for server state + job polling. Use the **frontend-design skill** for visual direction; do not ship default-template styling.

### 6.1 Navigation model (GCP-console-like)
- **Project switcher** in a persistent top bar (like GCP's project dropdown). Selecting a project scopes everything below it.
- Left nav within a project: **Search**, **Niche Dashboard**, **Category Sweep**, **Seed & Data**, **Settings**.

### 6.2 Surfaces
1. **Projects home** — grid of project cards (name, niche, seeded status, work/cluster counts, last activity). "New Project" CTA. This is the landing surface.
2. **New Project** — form: name, target BISAC (picker with the validated codes), keywords, intent config defaults. Creating a project does not auto-seed.
3. **Search (user surface)** — a prominent search box ("Search a book title or ISBN"). On submit → starts a live-search job → progress → results: clustered complaints (paraphrased), rating summary, demand/supply signals, provenance line, validity flags, charts, and Context Pack download. Clearly indicates historical+fresh vs fresh-only.
4. **Niche Dashboard** — browse the seeded project: top works, the niche-level complaint clusters, gap candidates, charts, summary KPIs. Empty state if not yet seeded ("Seed this niche to unlock historical depth — or search any title live").
5. **Category Sweep** — ranked BISAC gap candidates (the niche-level clusters), each expandable with flags, sample size, platforms, and a Context Pack export. Advanced-mode banner.
6. **Seed & Data (operator surface)** — trigger a seed (with meta/review/max-works inputs), live progress bar with step + %, history of past seed jobs, and the honest time estimate. Warns it's a long operation.
7. **Settings** — intent knobs only (timely↔evergreen, recency window, export size/token budget). Correctness knobs are NOT exposed (they live in `advanced.yaml`; see §11).

---

## 7. Data Visualization (§ explicit — real charts only)

Use a charting lib (Recharts or similar). **Only visualize data we actually have.** No price charts, no sales charts (we have neither — see §12).

Real, buildable visualizations:
- **Complaint aspect frequency** — bar chart of clustered aspects ranked by reviewer_count (the core "what readers complain about" view).
- **Rating distribution** — histogram per work (we have ratings).
- **Cluster composition** — size of each complaint cluster, with platform breakdown (corpus vs Hardcover).
- **Demand vs supply** — paired bars per BISAC candidate (demand proxies vs supply scarcity).
- **Gap candidates ranked** — horizontal bar of gap_score with confidence shading and flag badges.
- **Cross-platform agreement** — a clear indicator/gauge of the agreement %.
- **Provenance/coverage** — sample size and date-range chips, with a dimming "freshness" indicator tied to the timely↔evergreen setting (carry the existing concept).

Each chart shows its provenance and never implies more certainty than the sample supports.

---

## 8. Job & Loading UX (now a core feature, not polish)

- **Every async action is a job** with a consistent status component: queued → running (progress bar + step label) → done (auto-loads result) / error (clear message + retry).
- **Seed:** a real progress bar with % and current step ("scanning meta 250k/500k", "matching reviews", "clustering"), driven by the `jobs` table the seed writes to. The user can navigate away and come back; the job keeps running (subprocess).
- **Live search:** a lightweight inline spinner/progress (seconds), polling the job.
- **Model warm-up:** if `/health` reports models not yet loaded, show a one-time "warming up the analysis engine" state instead of failing.
- **Skeletons** for data panels while loading; **empty states** with a next action (never a blank panel or dead end); **error states** with retry and a plain-language cause.

---

## 9. Projects / Workspaces UX

- A project = an isolated niche (backend already enforces `project_id` isolation — reuse it; do not add per-row auth).
- Create, switch, delete from the UI. Switching a project rescopes all data.
- Two projects (e.g. "Programming" and "Cooking") coexist with zero data bleed — surface this as separate dashboards, GCP-style.
- A project can be browsed/searched even before it's seeded (live search works; niche depth is empty until seeded).

---

## 10. Configuration Surfacing (two-tier, carried from the engine)

- **Intent knobs → exposed in Settings UI:** timely↔evergreen slider, recency window, export max candidates + token budget, target niche/BISAC (on project create).
- **Correctness knobs → NOT in the UI:** min_critical_per_work, shrinkage, gate epsilon, normalization method, crosswalk thresholds, model revisions. These remain in `advanced.yaml`. Exposing them lets a user manufacture wrong results — keep them out, exactly as the engine PRD mandates.

---

## 11. Other Application Practices to Include

- **Onboarding empty state:** first run (no projects) → a guided "create your first project" flow.
- **Honest result framing:** every analysis result restates "treat as a hypothesis, not a finding," carrying the Context Pack's posture into the UI.
- **Thin-data honesty:** when clusters are degenerate/sparse, the UI says so (e.g. "low signal: N reviews, 1 cluster — interpret cautiously") rather than presenting it as confident output.
- **Graceful degradation:** Hardcover down → fresh layer unavailable, show historical-only with a notice; corpus not seeded → fresh-only.
- **Cancellation:** allow cancelling a running live-search job.
- **No dead ends:** every button does something; every empty state suggests a next action.

---

## 12. Explicitly OUT OF SCOPE (prevents the agent inventing things)

- **True sales data / Amazon BSR.** It is walled at $0 and is NOT in this product. Do **not** add a "sales" source, scraper, or fake metric. Traction is represented only by the proxies we have (ratings counts, read counts, review velocity), always labeled as proxies.
- **Multi-user auth / accounts.** Local, single-operator instances (you + CS friends each run their own). Projects are organizational, not per-user. No login system in v1.
- **Real-time corpus querying.** The corpus is batch-only, forever. Never on the live path.
- **Autocomplete on search (v1).** Exact/prefix match on submit is the v1. Type-ahead autocomplete is a documented later enhancement, not v1 scope.
- **Hosting/multi-tenant deployment.** Runs locally (uvicorn + next dev). Cloud deployment is out of scope.

---

## 13. Conflict Register — decisions locked to prevent downstream rework

These are the points most likely to cause conflicts mid-build. They are settled here; the agent must honor them and flag (per CLAUDE.md §2) before deviating.

1. **Engine is reused, never rewritten.** The backend imports `lacuna`. No reimplementation of adapters/NLP/scoring/export.
2. **Corpus = batch only. Hardcover = live.** No exceptions. The user-search path touches Hardcover, never the corpus scan.
3. **The live single-title path is NEW glue** (`live_single_title.py`) composing existing components — it is distinct from the existing seeded single-title analysis and from the batch seed.
4. **Models load once at backend startup, stay warm.** Live search never reloads them. The batch seed (subprocess) loads its own.
5. **Heavy CPU off the event loop** (worker pool). The batch seed is a subprocess.
6. **One job system** (`jobs` table) for all async work; the UI polls it. `analysis_runs` stays for engine observability.
7. **Frontend holds no secrets**; all source/engine calls proxy through the backend.
8. **Seeded data is dev scaffolding, not a product prerequisite.** Live search works with no seed.
9. **Sales data does not exist here.** Proxies only, always labeled.
10. **Correctness knobs stay out of the UI.** Intent knobs only.
11. **Streamlit is retired** (§14) — there is exactly one UI (Next.js) to avoid two drifting front ends. The CLI stays for operators.
12. **No new DB schema beyond `jobs`.** Reuse the existing tables and `project_id` isolation.

---

## 14. Streamlit & CLI Disposition

- **Streamlit dashboard: retire it.** Once the Next.js app covers browsing + search + sweep + seed-trigger, remove `app/streamlit_app.py` (and its tests) so there aren't two UIs drifting apart. Do this at the end, after parity is confirmed.
- **CLI: keep it.** `lacuna seed`, `analyze`, `sweep`, `export` remain for operators/power users and for the backend's seed subprocess. The CLI is not user-facing.

---

## 15. Security & Secrets Boundary

- All API keys (Hardcover, Google Books, NYT, optional Anthropic) live in `.env`, read by the **backend only**.
- The Next.js frontend never receives or embeds a key; it calls only the backend.
- `.env`, `.claude.json`, packs, and logs stay gitignored (carry the engine rules).
- CORS restricted to the local frontend origin.

---

## 16. Build Sequence (workstreams)

- **W1 — Backend skeleton:** FastAPI app, CORS, config reuse, model warm-load lifespan, `/health`, the `jobs` table migration, a jobs service.
- **W2 — Engine wrap (read paths):** projects CRUD, works/clusters/scores/candidates/export endpoints over the existing engine + DB.
- **W3 — Batch seed integration:** `POST /seed` → subprocess of existing CLI → progress into `jobs`. (Reuses the proven seed.)
- **W4 — Live single-title path (NEW glue):** `live_single_title.py` composing Hardcover pull + warm-model NLP + merge + score + export; `POST /search` as a job. **This is the riskiest new piece — build and verify it against a real title before the frontend depends on it (mirror the engine's G0 discipline).**
- **W5 — Frontend skeleton:** Next.js app, project switcher, navigation, TanStack Query, job-status component, design system per the frontend-design skill.
- **W6 — Surfaces:** Projects home/create, Search, Niche Dashboard, Category Sweep, Seed & Data, Settings — each wired to live endpoints, with empty/loading/error states.
- **W7 — Visualizations:** the §7 charts.
- **W8 — Polish & retire:** onboarding, honesty framing, graceful degradation, cancellation; then remove Streamlit; docs.

**Gate (mirrors the engine):** W4 (live search) must work against a real title before W6 builds UI that depends on it. Don't build the search UI on an unproven live path.

---

## 17. Acceptance Criteria

1. Backend starts, loads models once (visible via `/health`), serves all §4 endpoints; no secret ever reaches the client.
2. A user can **search a title that was never seeded** and get a live Hardcover-based result with provenance — proving the product needs no pre-seed.
3. A user searching a **seeded** title gets merged historical+fresh results with cross-platform agreement reflected in confidence.
4. The corpus is never scanned on a user search (verified: live search completes in seconds; only Hardcover is called).
5. An operator triggers a seed from the UI and watches a real progress bar (%/step) backed by the `jobs` table; navigating away doesn't kill it.
6. Two projects coexist with fully isolated dashboards.
7. The §7 charts render real data with provenance; no price/sales charts exist.
8. Every async action shows queued→running→done/error; no blank panels, no dead ends; thin/degenerate data is labeled honestly.
9. Correctness knobs are absent from the UI; only intent knobs are exposed.
10. Streamlit is removed; the CLI still works; one coherent UI remains.
11. `jobs` is the only schema addition; all engine internals are reused, not reimplemented.

---

## 18. CLAUDE.md Additions Needed (do before building)

Add a frontend section to `CLAUDE.md` so the agent doesn't improvise a different stack each session:
- Stack is fixed: FastAPI backend + Next.js (App Router, TS, Tailwind) frontend; engine is reused via import, never rewritten.
- The two-execution-model rule (corpus = batch, Hardcover = live) and the Conflict Register (§13) are binding.
- Use the frontend-design skill for all UI; use Context7 for FastAPI, Next.js, TanStack Query, and Recharts live docs.
- The W4 live-search gate: prove it on a real title before building dependent UI.

---

*The engine is the hard, finished 80%. This PRD is the product surface that makes it usable. Reuse relentlessly; the only genuinely new engine code is the live single-title glue in §3.2. Everything else is API + UI over what already works.*
