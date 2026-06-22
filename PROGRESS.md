# PROGRESS — Lacuna build state (for cold resume)

> Snapshot for picking up work in a fresh session. Pairs with `CLAUDE.md` (operating rules), `Lacuna_PRD.md` (engine spec), and `Lacuna_Frontend_PRD.md` (frontend/product spec). This file captures **transient state** those don't: branch topology, what's done vs in-flight, and exact resume commands.
>
> **Last updated:** 2026-06-22, mid-W8.

## TL;DR — where we are
The **engine** is built (on `main`). The **FastAPI backend (Plan A, W1–W4)** is complete and in **PR #1** (not merged). The **Next.js frontend (Plan B, W5–W7 + W8-polish)** is complete and committed. The **only unfinished build step is W8's Streamlit retirement**, then a final whole-branch review and the Plan B PR.

## Branch topology (verify with `git log --oneline --graph`)
- `main` = `a17771c` — engine only. **Plan A is NOT merged into main.**
- `feat/frontend-backend-w1-w4` (**Plan A**) = `9d9e4b7` — pushed; **PR #1** open at https://github.com/aleehjoo/Lucuna/pull/1 (do NOT merge yet). Includes a docs commit (`8ea60eb`, ancestor) that added CLAUDE.md §7 + both plan files + the Frontend PRD.
- `feat/frontend-ui-w5-w8` (**Plan B**, CURRENT, stacked on Plan A) = `ca238fd`.
  - **Pushed only through `8014d2d`.** Commits `407d708` (work-detail), `fb69e27` (W7 charts), `ca238fd` (W8 polish) are **committed locally but not yet pushed** — push the branch to back them up.
- Remote: `origin` = https://github.com/aleehjoo/Lucuna.git (note the repo name is "Lucuna").

## What's COMPLETE

### Engine (on `main`, pre-existing)
Adapters (Hardcover, Google Books, NYT, Open Library, Amazon corpus), local NLP (MiniLM embeddings + HDBSCAN + bart-large-mnli zero-shot labels), demand-gated scoring, Context Pack export, batch seed pipeline, Typer CLI. Supabase schema with `project_id` isolation. One niche seeded: **"Example - Programming & Software Books"** (~6 works, niche-level clusters, candidates) — known thin.

### Backend — Plan A, W1→W4 (`feat/frontend-backend-w1-w4`, PR #1)
New `api/` package wrapping the engine. All 12 tasks reviewed (spec+quality) + final whole-branch review (Opus) clean. DB-backed tests run live against Supabase.
- Migration `0003` (`jobs` table) — **applied to Supabase** (`alembic current` = `0003`). `jobs` is the ONLY schema addition.
- `EngineRuntime` warm-model singleton; FastAPI app factory (`api/app.py:create_app`, lifespan warm-load, CORS for :3000, `/health`).
- Endpoints: projects CRUD + PUT; reads (works/clusters/scores/candidates); **id-aware** Context Pack export; seed-as-subprocess + progress→`jobs`; job status + **cancel**; `POST /sweep` (**fire-and-forget**, disposes its own engine); `POST /search` (live single-title) + `live_single_title.py` glue.
- **W4 gate PROVEN** on a real title (`tests/test_live_search_gate.py`, recorded in `docs/METHODOLOGY.md`): "Atomic Habits" → 50 reviews, fresh_only, candidate flagged incomplete; HTTP e2e `POST /search` → job done in ~1.4s; corpus never scanned.

### Frontend — Plan B, W5–W7 + W8-polish (`feat/frontend-ui-w5-w8`, current)
Next.js 16 App Router + TS + Tailwind v4 in `frontend/`. TanStack Query + Recharts. **100/100 frontend tests pass, tsc clean, build succeeds** as of `ca238fd`.
- **W5** — scaffold; design system ("ink & vellum / negative-space" identity: cool paper, ultramarine, gold-leaf, Fraunces/Inter/IBM Plex Mono); API client + typed DTOs + Query provider + job-polling hook (stops on terminal); app shell (top bar, project switcher, left nav, health indicator); `JobStatus` component. **Design direction approved by user.**
- **W6** — all surfaces wired to live data: Projects home + onboarding, New Project, **Search** (leads with rating/sample/provenance/fresh-only; clusters a bonus; honest `low_signal` when empty), **Niche Dashboard** (works, niche clusters, gap candidates, KPIs), Category Sweep, Seed & Data (navigation-survivable progress), Settings (intent knobs only, correctness-knobs-absent guard test). **work-detail page** added (`407d708`) — the dashboard dead-end 404 is FIXED. **User clicked through and approved.**
- **W7** (`fb69e27`) — Recharts visualizations: AspectFrequency, RatingHistogram, DemandSupply (labeled "popularity proxy, not sales"), AgreementGauge, ProvenanceChips, and the **Gap Strip signature**, wired into Search/Dashboard/Sweep. Charts carry an `sr-only` data list (accessibility + testable). **Gap Strip judgment call (per user): SHIPS** — against the real all-zero seeded `gap_score`s it renders a deliberate honest note ("Gap scores need demand signals, which aren't present in a $0 corpus-only run…"), NOT broken empty bars; gold-leaf negative-space bars only render when real gap variation exists.
- **W8-polish** (`ca238fd`) — `HypothesisBanner` on result surfaces; Search 503 (no Hardcover key) → non-alarming notice; `useCancelJob` + cancellable `JobStatus` (live-search cancel → "Cancelled" terminal state); no-dead-ends audit.

## IN FLIGHT / NEXT (do these in order)
1. **W8 — retire Streamlit + docs** (NOT started; its subagent dispatch failed on a safety-classifier outage). The work:
   - Confirm parity first (Frontend PRD §14): Next.js covers browse/search/sweep/seed-trigger — it does (W5–W8).
   - Delete `app/streamlit_app.py` and any streamlit-only test (grep `tests/` for `streamlit`/`app.streamlit_app`). The CLI (`app/cli.py`) **stays**.
   - Remove `streamlit>=1.36` from `pyproject.toml` IF nothing else imports streamlit (grep `lacuna/ api/ app/ scripts/ tests/` first).
   - Remove the stale `streamlit` item from `CLAUDE.md` §6's Context7 list (that one line only).
   - Update `README.md` to the FastAPI + Next.js run path (commands below); remove "run Streamlit" instructions. Leave historical PRD/old-plan markdown alone.
   - Verify: `.venv\Scripts\pytest.exe -q` green (no orphaned streamlit-test imports); `cd frontend && npm run build` still succeeds.
   - Commit: `chore: retire Streamlit dashboard (Next.js is the one UI); docs for FastAPI+Next.js stack`.
2. **Plan B final whole-branch review** — broad review across W5–W8 (commits `9d9e4b7..HEAD`), most-capable model; fix any Critical/Important; sanity-check Frontend PRD §17 acceptance.
3. **Open Plan B PR** — push `feat/frontend-ui-w5-w8`, open a PR (stacked on Plan A's PR #1). **Do NOT merge.**

## KNOWN ISSUES / deferred (none blocking; logged for follow-up)
- **work-detail 404: FIXED** in `407d708` (was a dead end; now a real page with 404→EmptyState).
- **Thin clusters / all-zero gap_scores:** the seed is genuinely thin and corpus-only runs withhold demand, so `gap_score` is 0.0 for every candidate and live single-title search often yields **0 complaint clusters**. This is handled honestly everywhere (rating/provenance lead, `low_signal` notes, Gap Strip degenerate state) — it is the data reality, not a bug. More volume needs a wider `--review-limit` seed and/or seeded demand signals.
- **`PUT /projects/{id}` does full-replace on `config`,** not merge (no second writer today; footgun if a future feature writes another `config` key — Settings would clobber it). Deferred.
- **BISAC code labels are hardcoded** in New Project (no backend endpoint serves the validated set).
- **Settings export-token-budget input floor is 0** (was a min/step-mismatch fix; harmless but odd).
- **Context Pack download uses raw `fetch`** (Search/Sweep) rather than the typed `api` client (md returns text). Works; cleanup only.
- **No cross-project isolation test** asserting project A's data can't leak into B (code is correct on inspection; add one test).
- **`/search` job has no intermediate progress** (jumps resolving→done); `analyze_live` accepts `progress_cb` but `/search` doesn't pass one.
- **`list_projects` does O(2N+1) count queries** (fine at operator scale).
- **Seed/sweep jobs can be stuck `running`** if the process restarts mid-run (pre-existing; a startup janitor marking orphaned jobs `error` is the fix).

## EXACT RESUME COMMANDS
```bash
# you are here:
cd C:/Users/Alejandro/Documents/Lacuna
git checkout feat/frontend-ui-w5-w8        # Plan B branch; HEAD should be ca238fd (or later)
git status                                  # expect clean

# --- run the product (two terminals) ---
# backend (loads NLP models; reads .env for DATABASE_URL + HARDCOVER_API_TOKEN):
.venv\Scripts\uvicorn.exe api.app:create_app --factory --host 127.0.0.1 --port 8000
# frontend:
cd frontend && npm run dev                  # http://localhost:3000  (talks to NEXT_PUBLIC_API_BASE, default :8000)

# --- tests ---
cd frontend && npm run test && npx tsc --noEmit && npm run build   # frontend (no DB needed)
# backend tests are DB-gated; load DATABASE_URL from .env WITHOUT printing it, then run:
#   $line = Get-Content .env | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
#   $env:DATABASE_URL = ($line -replace '^DATABASE_URL=', '').Trim('"')
.venv\Scripts\pytest.exe -q                 # full backend suite (live W4 gate test is slow if HARDCOVER_API_TOKEN set)

# --- CLI (operators) still works ---
.venv\Scripts\lacuna.exe seed|analyze|sweep|export ...
.venv\Scripts\alembic.exe current           # should show 0003 (head)
```

## THINGS A FRESH SESSION NEEDS RE-TOLD (not in CLAUDE.md / PRDs)
- **Execution method:** this build is being run **subagent-driven** (superpowers `subagent-driven-development`): one implementer subagent per task, then a task reviewer (spec+quality), fix-loop on Critical/Important, broad whole-branch review at the end. Implementation plans live at `docs/superpowers/plans/2026-06-19-lacuna-frontend-backend-w1-w4.md` (Plan A) and `…-frontend-ui-w5-w8.md` (Plan B).
- **Durable progress ledger:** `.git/sdd/progress.md` — one line per completed task (commit ranges + review status + noted minors). **Trust it + `git log` over memory after any interruption; do not re-dispatch tasks it marks complete.** Task briefs/reports are in `.git/sdd/*.md`.
- **Windows / venv:** `uv` is NOT on PATH in non-interactive shells — run everything via `.venv\Scripts\*.exe` (pytest, alembic, uvicorn, lacuna). The venv now has `pip` (bootstrapped via ensurepip).
- **DB-gated tests** check `os.getenv("DATABASE_URL")` and SKIP without it — to actually exercise Supabase, export DATABASE_URL from `.env` first (snippet above). **Never print/commit the connection string, Hardcover token, or any secret.**
- **Stacked branches:** Plan B sits on top of Plan A; Plan A's PR #1 must merge first, then Plan B rebases onto main. Neither is merged yet (user's call).
- **Session-limit interruptions** have repeatedly cut subagents off mid-task (B-Task 12, W7) — **always verify a cut-off task's real state from git + run the tests before trusting its report or committing**; a couple landed uncommitted/failing and had to be finished.
- **One subagent (W7) falsely claimed `Lacuna_PRD.md` was prompt-injected** — VERIFIED FALSE (the file is clean/unmodified; it misattributed real harness reminders). The PRD is fine.
- **frontend/AGENTS.md + frontend/CLAUDE.md** were auto-generated by create-next-app (separate from root CLAUDE.md; harmless).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
