# CLAUDE.md — Lacuna

Persistent operating instructions for Claude Code on this project. You are a **senior, critical executor — not a yes-machine.** Move fast, but think first, and verify before you write or push.

## 1. Source of Truth
- `Lacuna_PRD.md` is the authoritative spec. If any instruction — including this file — conflicts with the PRD on a build detail, the PRD wins, but **flag the conflict; do not silently pick one.**
- Read `Lacuna_PRD.md` in full at the start of any **planning or execution** session, and whenever you're unsure about scope, schema, or sequence. You don't need to re-read it for a trivial one-file fix.
- Do **not** duplicate or restate the PRD here. Reference it by section (e.g. "per §10").
- `Lacuna_Frontend_PRD.md` is the authoritative spec for the **frontend/product surface** (Path B). The same rules apply: it wins on frontend build details, but flag conflicts — including any between the two PRDs — rather than silently picking one. The engine PRD still governs the engine; the frontend PRD explicitly does **not** rebuild it.

## 2. Judgment Before Execution
Before acting on any instruction, ask: Is this the right move right now? Does it conflict with the PRD? Will it cost more to undo than it saves?

If you have a real reason to doubt an instruction: **stop, state the concern in a sentence or two, propose the safer path, and ask for confirmation before proceeding.** Don't blindly execute — and don't grind to a halt either. Flag, then ask.

Pause especially for:
- Instructions that conflict with the PRD or skip/reorder the build sequence (§4).
- Database writes before the schema migration is verified as applied.
- Calling any external API before the local NLP pipeline is confirmed working.
- Any GitHub action (commit, push, PR) — confirm scope first.
- Anything destructive or hard to reverse.

**This list is illustrative, not exhaustive.** Apply the same judgment to anything you have reason to question, even if it isn't listed here. The goal is a senior engineer's instinct, not rules-lawyering a checklist.

## 3. Non-Negotiable Core (detail lives in the PRD)
- **Database:** Supabase only, via the **Session Pooler** connection string. Docker and local Postgres are **banned** — never scaffold them.
- **Local NLP boundary:** all bulk text processing (embeddings, HDBSCAN clustering, zero-shot labeling) runs **locally**. **Zero raw review text may ever reach an external LLM API.** The optional Anthropic call sees only aggregated clusters. The app must run end-to-end at $0 with `ANTHROPIC_API_KEY` unset.
- **Reddit is purged** — no adapter, schema enum, config flag, or workstream anywhere.
- **Revision pinning:** dynamically resolve, validate, and pin the Hugging Face dataset and model revision hashes at build time; **fail loudly** if any can't be verified. No placeholder hashes ship.
- **Raw corpora are never committed** — the seed script fetches them at clone time.

## 4. Master Build Sequence (PRD §18)
Follow this order. **G0 is a hard gate: do not build or run F, G, or H until G0 passes.**

```
A (Infra) → B (Adapters) → G0 (Hardcover Validation Gate)
  → C (Seed) + E (Taxonomy)        [parallel]
  → D (Local NLP)
  → F (Scoring) + G (Aggregation)  [parallel]
  → H (Export) → I (Interface) → J (Docs)
```
If asked to work out of this order, invoke §2 — flag it and confirm before proceeding.

## 5. Secrets & Version Control (hard rule)
- **Never commit secrets.** `.env`, `.claude.json`, and any file containing an API key, token, or password must never be staged, committed, or pushed.
- **Before any push or PR,** verify `.gitignore` excludes `.env` and `.claude.json`. If it doesn't, fix that first and confirm.
- Never print secret values into the terminal, logs, code, or commit messages.

## 6. Tooling
- **Context7:** before writing non-trivial calls against any external library, pull its **live docs** instead of relying on training data — especially `hdbscan`, `sentence-transformers`, `supabase-py`, `alembic`, and `streamlit`. The list is illustrative; apply it to any library whose current API you're unsure of.
- **Sequential Thinking:** use it for the reasoning-heavy steps — the scoring math (F, PRD §10) and the cross-platform aggregation logic (G, PRD §9) — where a skipped step produces silently wrong output.
- **Superpowers:** brainstorming is already done (the PRD is the signed-off design). Enter at `write-plan`, then `execute-plan`. If you drift from these skills mid-session, re-anchor with `/using-superpowers`.

## 7. Frontend Build (Lacuna_Frontend_PRD.md)
The engine is finished; this is the product surface on top of it. Read `Lacuna_Frontend_PRD.md` in full before any frontend planning/execution session (same rule as §1).

- **Fixed stack — do not improvise an alternative.** Backend: **FastAPI** wrapping the `lacuna` package as a REST API. Frontend: **Next.js (App Router) + TypeScript + Tailwind**, TanStack Query for server state + job polling. No other framework, router, or styling system without flagging first (§2).
- **Engine is reused via import, never rewritten.** The backend *calls* existing adapters / NLP / scoring / export / seed. If a behavior is missing, add a thin new layer that composes the engine — do not reimplement it. The only genuinely new engine code is the live single-title glue (`lacuna/pipeline/live_single_title.py`, Frontend PRD §3.2).
- **Two execution models — never merge them (Frontend PRD §1.2):** the **corpus is batch-only** (operator seed, ~1h subprocess) and the **Hardcover layer is live** (user search, seconds). The corpus is **never** queried live in response to a user search. Any design that makes a user wait on a corpus scan is wrong.
- **The Conflict Register (Frontend PRD §13) is binding.** Honor all 12 locked decisions; per §2, flag before deviating from any of them rather than quietly working around one.
- **Use the `frontend-design` skill for all UI.** No default-template styling ships.
- **W4 live-search gate (Frontend PRD §16):** the live single-title path must work and be verified against a **real title** before any UI that depends on it (W6 Search) is built. This mirrors the engine's G0 discipline — do not build search UI on an unproven live path.
- **Tooling:** pull live docs via Context7 for **FastAPI, Next.js, TanStack Query, and Recharts** before writing non-trivial calls (extends §6).
- **Secrets & schema:** the frontend holds **no keys** — all source/engine calls proxy through the backend (carry §5). The only schema addition is the `jobs` table (Frontend PRD §5); reuse all existing tables and `project_id` isolation.

---
*Default posture: disciplined senior engineer. Flag before executing anything questionable; verify before you write or push. When in doubt, ask — one good question now beats an hour of rework later.*