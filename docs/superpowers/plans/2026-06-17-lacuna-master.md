# Lacuna — Master Implementation Plan (Index & Sequencing)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement the per-workstream plans task-by-task. This master file is the **index and gate map** — it is not executed directly. Execute the per-workstream plan files in the order below. Steps in those files use checkbox (`- [ ]`) syntax.

**Goal:** Build Lacuna — a local, $0-runtime engine that surfaces evidence-backed hypotheses about reader dissatisfaction in a book niche, aggregating review sentiment across platforms, demand-gating it, and exporting an LLM-ready Context Pack — against a Supabase database, per `Lacuna_PRD.md` v3.0.

**Architecture:** One local Python app. Bulk NLP (embeddings + HDBSCAN + zero-shot labeling) runs locally and free; raw review text never reaches an external LLM API. Distilled output only is written to Supabase (managed Postgres + pgvector) over the Session Pooler `DATABASE_URL`. Adapters isolate every external contract behind pydantic boundaries. Scoring is resilient by construction (missing ≠ zero, soft demand gate, weighted geometric mean).

**Tech Stack:** Python 3.11+ (3.12.10 present), `uv` package manager, SQLAlchemy 2.x async + asyncpg + alembic + pgvector, pydantic v2, httpx + gql, sentence-transformers (`all-MiniLM-L6-v2`), transformers (`facebook/bart-large-mnli`), hdbscan + scikit-learn + scipy, polars + duckdb, datasets + huggingface_hub, streamlit, typer.

---

## 0. How to use this index

The PRD (§18) defines 10 workstreams with a **hard gate at G0**. Each workstream has its own detailed plan file in this directory. Execute strictly in the sequence below. **Do not build or run F, G, or H until G0 passes** (CLAUDE.md §4, PRD §18).

| Order | Workstream | Plan file | Depends on | Status |
|------|------------|-----------|-----------|--------|
| 1 | **A — Infra** | `2026-06-17-lacuna-A-infra.md` | none | ✅ written |
| 2 | **B — Adapters** | `2026-06-17-lacuna-B-adapters.md` | A | ✅ written |
| 3 | **G0 — Hardcover Validation Gate** ⛔ | `2026-06-17-lacuna-G0-validation-gate.md` | A, B (Hardcover adapter) | ✅ written |
| 4 | **C — Seed & works grouping** | `2026-06-17-lacuna-C-seed.md` | A, B | ⏳ pending go |
| 4 | **E — Taxonomy** (parallel with C) | `2026-06-17-lacuna-E-taxonomy.md` | A, B | ⏳ pending go |
| 5 | **D — Local NLP** | `2026-06-17-lacuna-D-nlp.md` | A, C | ⏳ pending go |
| 6 | **F — Scoring** (parallel with G) | `2026-06-17-lacuna-F-scoring.md` | D, E, G0 | ⏳ pending go |
| 6 | **G — Aggregation** (parallel with F) | `2026-06-17-lacuna-G-aggregation.md` | B, D, G0 | ⏳ pending go |
| 7 | **H — Export** | `2026-06-17-lacuna-H-export.md` | F, G, G0 | ⏳ pending go |
| 8 | **I — Interface** | `2026-06-17-lacuna-I-interface.md` | F, G, H | ⏳ pending go |
| 9 | **J — Docs & tests** | `2026-06-17-lacuna-J-docs.md` | all | ⏳ pending go |

```
A → B → ⛔ G0 (gate) → (C, E parallel) → D → (F, G parallel) → H → I → J
```

> **Why C–J are deferred:** G0 is a hard gate (PRD §18). Whether Hardcover actually returns live review data on niche titles is unknown until G0 runs; that result can change the fusion/scoring design (the "fresh" sentiment layer). Plans C–J are written *after* the gate result is known, so they reflect reality instead of an assumption. The user opted to generate A → B → G0 first.

---

## 1. Flagged environment assumptions (raised before execution, per CLAUDE.md §2)

These were verified on this machine on 2026-06-17 and are handled inside Workstream A — listed here so they are not a surprise mid-build:

1. **`uv` is not installed.** The entire PRD toolchain (`uv sync`, `uv run …`) depends on it. Workstream A Task A1 installs it via the official installer. *(Assumption: network access to `astral.sh` is available.)*
2. **The directory is not a git repository.** The plans use per-task commits (writing-plans skill). Workstream A Task A0 runs `git init` and writes `.gitignore` **excluding `.env` and `.claude.json` before any other file is created** (CLAUDE.md §5).
3. **Python 3.12.10 is present** — satisfies "3.11+". `uv` will still pin the interpreter in `pyproject.toml` (`requires-python = ">=3.11"`).
4. **Supabase project is the user's responsibility** (PRD §3). The plan assumes the user has: created a project, set a DB password, enabled the `pgvector` extension in the dashboard, and pasted the **Session Pooler** URL into `.env`. Migrations (Task A9) will fail loud if this is not done — that is the intended behavior, not a bug to work around.
5. **API keys** (`HARDCOVER_API_TOKEN`, `GOOGLE_BOOKS_API_KEY`, `NYT_BOOKS_API_KEY`) must be in `.env` before B/G0. `ANTHROPIC_API_KEY` stays **unset** by default (the $0 path, PRD §17.5).
6. **Model/dataset download size:** revision pinning (Task A8) and the NLP workstream download `all-MiniLM-L6-v2` (~90 MB) and `bart-large-mnli` (~1.6 GB) to the local HF cache. This is expected and one-time.

## 2. Flagged PRD-gap resolutions (approved 2026-06-17 — proceed with defaults, document in METHODOLOGY.md)

The PRD specifies the *shape* of these but not exact numbers/formulas. Resolutions are added as **tunable knobs** so they are visible and overridable, never silently hard-coded:

1. **Time-skew guard (PRD §10)** — added to `config/advanced.yaml`:
   - `recent_supply_surge_threshold: 0.30` — `recent_title_count / title_count` above this ⇒ `recent_supply_surge=true`.
   - `recent_supply_surge_downweight: 0.7` — multiply `gap_score` by this when surge is set.
2. **Cross-platform cluster merge (PRD §9)** — added to `config/advanced.yaml`:
   - `cluster_merge_similarity: 0.75` — cosine cutoff on cluster-label embeddings to merge clusters across platforms (distinct from `crosswalk_auto_accept`, which governs taxonomy mapping).
3. **Confidence formula (PRD §10)** — explicit composite, documented in METHODOLOGY.md (Workstream F plan, `validity.py`):
   `confidence = clamp01( min(1, sample_size/min_sample_gate) * (0.7 ** imputed_layer_count) * (0.85 if single_platform else 1.0) * crosswalk_conf )`.
4. **Raw component derivation (PRD §9/§10)** — a dedicated `lacuna/scoring/components.py` builds `(value, present)` for `demand`, `supply_scarcity`, `unmet_need` from the distilled tables (defined in the Workstream F plan). `present=False` ⇒ absent (never zero); `present=True, value=0.0` ⇒ genuine zero (propagates).

## 3. Full file map (PRD §2)

```
lacuna/
├─ pyproject.toml                 [A]
├─ uv.lock                        [A]
├─ .env.example                   [A]
├─ .gitignore                     [A]
├─ config/
│  ├─ default.yaml                [A]   INTENT knobs
│  └─ advanced.yaml               [A]   CORRECTNESS knobs (+ pinned revisions, + flagged knobs §2)
├─ alembic.ini                    [A]
├─ alembic/
│  ├─ env.py                      [A]   async env
│  └─ versions/0001_initial.py    [A]   §5 schema + pgvector
├─ scripts/pin_revisions.py       [A]   resolve+verify+pin HF hashes (fail loud)
├─ lacuna/
│  ├─ __init__.py                 [A]
│  ├─ config.py                   [A]   config+env load; DATABASE_URL scheme normalization
│  ├─ db/{models.py,session.py}   [A]
│  ├─ schemas/                    [B]   pydantic boundary models per source
│  ├─ adapters/                   [B]   corpus, hardcover, google_books, nyt, open_library, _http
│  ├─ seed/                       [C]   seed.py, works_grouping.py, normalization.py (VERSIONED)
│  ├─ nlp/                        [D]   embeddings.py, clustering.py, aspects.py
│  ├─ taxonomy/                   [E]   bisac.py, crosswalk.py
│  ├─ scoring/                    [F]   components.py, normalize.py, gap_score.py, validity.py
│  ├─ aggregation/                [G]   cross_platform.py
│  ├─ export/                     [H]   context_pack.py
│  └─ pipeline/                   [F/G/H/I] single_title.py, category_sweep.py, validation.py [G0]
├─ app/{streamlit_app.py,cli.py}  [G0 starts cli.py; I completes]
├─ tests/                         [B/F/G/J] contract, scoring, hardcover validation
├─ docs/{METHODOLOGY.md,LIMITATIONS.md}  [J]
└─ README.md                      [J]
```

## 4. Cross-cutting conventions (apply in every workstream)

- **TDD:** every behavior gets a failing test first, then minimal code, then green, then commit (writing-plans skill).
- **Commits:** one per task minimum, conventional-commit messages. Never `git add .` blindly — stage explicit paths (avoids staging `.env`).
- **Secrets:** `.env`, `.claude.json` never staged/committed/logged (CLAUDE.md §5). Verified by a test in Workstream A.
- **Local NLP boundary (PRD §7):** nothing in `nlp/`, `seed/`, `aggregation/` may call an external LLM API. The only Anthropic call lives in `export/` and receives aggregated clusters only.
- **No Reddit** anywhere (PRD §17.12) — checked by a repo-grep test in Workstream J.
- **No Docker / local Postgres** anywhere (CLAUDE.md §3) — Supabase only.
- **Boundary validation:** pydantic v2 models on every external response; shape drift fails loud.
- **Context7 first** for non-trivial library calls; **Sequential Thinking** for F and G math (already done — see each plan's "Design notes").

## 5. Acceptance criteria → workstream map (PRD §17)

| # | Criterion | Proven in |
|---|-----------|-----------|
| 1 | `alembic upgrade head` provisions full schema; no Docker/local PG | A |
| 2 | `validate-hardcover` passes before fusion/scoring | G0 |
| 3 | `seed` populates distilled tables, local NLP, zero raw files committed | C, D |
| 4 | HF dataset+model revisions resolved/validated/pinned; no placeholders | A |
| 5 | Runs end-to-end with `ANTHROPIC_API_KEY` unset; $0 | D, H |
| 6 | `analyze --isbn` ≤~2 min, clustered complaints + provenance + pack | F, H, I |
| 7 | Hardcover normalized per platform, fused, agreement in confidence | G |
| 8 | Missing≠0, genuine 0 propagates, blind_spot, surge, geomean+gate | F |
| 9 | Both modes ship | I |
| 10 | Two projects isolated via project_id | A (schema), I |
| 11 | Provenance on every panel; dimming freshness slider; no dead ends | I |
| 12 | No Reddit anywhere | J (grep test) |
| 13 | Contract tests pass incl. Hardcover live check; uv.lock + pins present | B, G0, J |

---

## Self-review (against PRD)

- **Spec coverage:** every §18 workstream has a row in §0 with a plan file and dependency; every §17 criterion is mapped in §5. Gaps surfaced in §2 are resolved with approved defaults.
- **Sequencing:** the G0 hard gate is encoded as a blocking row and a "why deferred" note; F/G/H explicitly list `G0` as a dependency.
- **Secrets/Reddit/Docker bans** each have an enforcing test assigned (A, J).

## Execution handoff

A → B → G0 are written and ready. After G0 passes, return here and request the C/E → D → F/G → H → I → J plans (they will be authored against the real gate result).
