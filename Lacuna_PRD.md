# Lacuna — Product Requirements Document (Final Execution Specification)

**Version:** 3.0 — definitive, execution-ready
**Build agent:** Claude Code (parallelize across the subagent workstreams in §18)
**Deployment:** Local application, **Supabase** database. No Docker, no local Postgres, no hosted app server.
**User's total responsibility:** populate `.env` (one Supabase Session Pooler URL + three API keys), run database migrations, run the seed command once, launch the app. Nothing else.

---

## 0. Build Brief (read first)

- **What you are building:** one local Python application called **Lacuna**. It finds what readers of existing books are dissatisfied with in a target niche, by aggregating real review sentiment across platforms, gating it against demand so dissatisfaction only counts where reader attention exists, and exporting an **LLM-ready Context Pack** the user feeds into their own model.
- **Two modes, both first-class and non-negotiable:**
  - **Single-Title Watchlist mode** — analyze and track specific titles by ISBN/ASIN/title. Fast, statistically clean. The primary path.
  - **Category Sweep mode** — macro analysis of a whole BISAC niche. Slower first run, lower confidence, fused at the BISAC-bucket level, flagged as advanced — but a required, shipping mode.
- **Database:** **Supabase** is the one and only database infrastructure. The app connects via a single `DATABASE_URL` (the Supabase **Session Pooler** string). `pgvector` is enabled on the Supabase project.
- **Hard commitments baked into the architecture (do not let these drift):**
  1. All bulk text analysis runs **locally and free** (embeddings + HDBSCAN clustering + local zero-shot labeling). Raw review text is **never** sent to an external LLM API. Runtime budget is strictly $0.
  2. The gap score is demand-gated and **resilient**: a single missing or glitched layer never collapses the score to zero (§10).
  3. Every output carries provenance (review count, platforms, date range, confidence). Missing data lowers confidence; it never inflates a score.
  4. Cross-platform **agreement** (Amazon corpus ∩ Hardcover) is the credibility signal.
  5. Raw third-party corpora are never committed to the repo — the seed script fetches them at clone time.
  6. Dataset and model revisions are **dynamically resolved, validated, and pinned at build time** — no placeholder hashes ship (§15).
- **User-facing setup:** the only manual step a human performs is filling `.env` and running three commands. The README ships the click-by-click Supabase + key-acquisition guide.

---

## 1. What Lacuna Is

A local, $0-runtime engine that surfaces **evidence-backed hypotheses about reader dissatisfaction** in a target niche. It delivers signal; the user and their LLM interpret it. It is a hypothesis generator over reader sentiment, **not** a sales-rank tool.

**Core design commitments (non-negotiable):**
1. Bulk sentiment tagging is **local-only** (embeddings + clustering + zero-shot). The LLM API is never sent raw review text and is optional.
2. Dissatisfaction is demand-gated — a complaint scores only where reader attention exists, via a **soft** gate that dampens rather than annihilates.
3. Scoring is resilient to missing/failed layers (§10): missing ≠ zero.
4. Every output carries provenance; cross-platform agreement raises confidence.
5. Raw corpora are fetched at clone time, never committed.

---

## 2. Tech Stack & Repository Structure

**Stack:**
- Python 3.11+, dependency management via `uv` (commit `uv.lock`).
- **Supabase** (managed PostgreSQL 15 + `pgvector`). The app holds no database of its own — it connects to Supabase over `DATABASE_URL` (Session Pooler).
- Hugging Face `datasets` (streaming mode) for the Amazon corpus.
- `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim) for embeddings; `transformers` (`facebook/bart-large-mnli`) for local zero-shot aspect labeling. Revisions resolved + pinned at build time (§15).
- `hdbscan` + `scikit-learn` for clustering.
- `polars` + `duckdb` for local heavy data wrangling during the seed pass.
- `httpx` for REST clients, `gql`/`httpx` for Hardcover GraphQL, `pydantic` v2 for boundary validation.
- `alembic` for migrations, `sqlalchemy` 2.x (async) for DB access. The async Postgres driver requires a `postgresql+asyncpg://` scheme on `DATABASE_URL` — the config layer normalizes a pasted Supabase `postgresql://` string to the correct driver scheme automatically.
- `streamlit` for the dashboard, `typer` for the CLI.
- Anthropic SDK — **optional**, used only for the convenience "local narrative" toggle (§12). The export is fully functional with no LLM key.

**Repository layout:**
```
lacuna/
├─ pyproject.toml
├─ uv.lock
├─ .env.example
├─ config/
│  ├─ default.yaml               # INTENT knobs + target niche (user-editable)
│  └─ advanced.yaml              # CORRECTNESS knobs (warned, rarely touched)
├─ alembic/                      # migrations (creates schema + enables pgvector)
├─ lacuna/
│  ├─ config.py                  # loads + validates config + env; normalizes DATABASE_URL scheme
│  ├─ db/                        # models.py, session.py
│  ├─ schemas/                   # pydantic boundary models per source
│  ├─ adapters/                  # corpus.py, hardcover.py, google_books.py,
│  │                            #   nyt.py, open_library.py
│  ├─ seed/                      # seed.py, works_grouping.py, normalization.py (VERSIONED)
│  ├─ nlp/                       # embeddings.py, clustering.py, aspects.py
│  ├─ taxonomy/                  # bisac.py, crosswalk.py
│  ├─ scoring/                   # gap_score.py, normalize.py, validity.py
│  ├─ aggregation/               # cross_platform.py
│  ├─ export/                    # context_pack.py
│  └─ pipeline/                  # single_title.py, category_sweep.py
├─ app/
│  ├─ streamlit_app.py
│  └─ cli.py
├─ tests/                        # contract tests (recorded responses), scoring tests, hardcover validation
├─ docs/
│  ├─ METHODOLOGY.md
│  └─ LIMITATIONS.md
└─ README.md
```
(No `docker-compose.yml`. No local Postgres. The database is Supabase.)

---

## 3. Environment & Secrets (the user's only manual step)

`.env.example` (ship with empty values; user copies to `.env` and fills):
```bash
# DATABASE — Supabase Session Pooler connection string (IPv4-compatible).
# From the Supabase dashboard: click "Connect", choose the "Session pooler" string,
# and replace [YOUR-PASSWORD] with your database password. Do NOT use the Direct
# connection string (IPv6-only on the free tier and fails on most home networks).
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres

# Fresh sentiment + demand/supply sources
HARDCOVER_API_TOKEN=          # hardcover.app/account/api — paste the eyJ... token WITHOUT "Bearer "
GOOGLE_BOOKS_API_KEY=         # Google Cloud Console → enable Books API → create API key
NYT_BOOKS_API_KEY=            # developer.nytimes.com → new app → enable Books API

# Optional — local LLM narrative in the export (export works WITHOUT this)
ANTHROPIC_API_KEY=

# No key required: the McAuley Amazon corpus (public HF dataset) and Open Library.
```
Supabase prerequisites, performed once in the dashboard (documented in the README): create the project and set a database password; enable the `pgvector` extension (Database → Extensions → search `vector` → enable); copy the **Session Pooler** connection string. Secrets are read only server-side via `lacuna/config.py`; `.gitignore` excludes `.env`; secret values are never logged.

---

## 4. Data Sources & Adapters

Each adapter lives in `lacuna/adapters/`, returns **pydantic-validated** models (validation at the boundary so a source changing shape fails loud), and carries its own rate/retry policy with exponential backoff + jitter on 429/5xx, honoring `Retry-After`.

| Source | Role | Auth | Limits to enforce | Notes |
|---|---|---|---|---|
| **McAuley Amazon Reviews 2023** (HF `McAuley-Lab/Amazon-Reviews-2023`, configs `raw_review_Books` / `raw_meta_Books`) | Deep historical sentiment (≤ Sep 2023) | none (public) | stream, never full-download | Revision hash resolved + pinned at build (§15). Load raw parquet; avoid script loaders/`trust_remote_code`. Never commit its text. |
| **Hardcover** (`https://api.hardcover.app/v1/graphql`) | Fresh sentiment (live reviews/ratings) | Bearer token (expires yearly) | **60 req/min**, 30s query timeout, server-side only, send a descriptive User-Agent | Coverage incomplete on niche titles — supplement with Google Books/Open Library. Subject of the early validation gate (§18). |
| **NYT Books API** | Fresh demand (bestseller presence) | API key | 4,000/day, 10/min (≈6s spacing) | Coarse but real selling signal. |
| **Google Books API** | Demand (ratings counts) + BISAC anchor | API key | ~1,000/day | Categories are BISAC-derived → bootstrap the crosswalk (§5 / §9). |
| **Open Library** | Supply (title counts, recency) | none | be polite, descriptive User-Agent | Subject search + edition data; provides post-cutoff title counts for the time-skew guard. |

(Reddit has been removed entirely from the architecture.)

---

## 5. Database Schema (Supabase / PostgreSQL + pgvector)

Distilled output only — never the raw corpus. Money in integer cents, timestamps `timestamptz` UTC. Migrations in `alembic/`; the first migration enables the extension (the project must also have it toggled on in the Supabase dashboard).

```sql
create extension if not exists vector;

-- WORKSPACES: isolate niches (one project = one niche)
create table projects (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  target_bisac   text[] not null,
  subject_filter jsonb not null default '{}',
  config         jsonb not null default '{}',
  created_at     timestamptz not null default now()
);

-- WORKS (the abstract book) + EDITIONS (format variants)
create table works (
  id              uuid primary key default gen_random_uuid(),
  project_id      uuid not null references projects(id) on delete cascade,
  normalized_key  text not null,
  norm_version    int not null,
  title           text not null,
  author          text,
  primary_bisac   text,
  first_pub_year  int,
  edition_count   int not null default 0,
  agg_rating_avg  numeric(3,2),
  agg_rating_count int not null default 0,
  agg_rating_bayes numeric(3,2),
  unique (project_id, normalized_key)
);

create table editions (
  id           uuid primary key default gen_random_uuid(),
  work_id      uuid not null references works(id) on delete cascade,
  project_id   uuid not null references projects(id) on delete cascade,
  asin         text,
  parent_asin  text,
  isbn13       text,
  isbn10       text,
  format       text check (format in ('kindle','paperback','hardcover','audiobook','other')),
  price_cents  int,
  rating_avg   numeric(3,2),
  rating_count int,
  unique (project_id, asin)
);

-- UNIFIED REVIEWS across platforms (curated critical subset only)
create table reviews (
  id            bigint generated always as identity primary key,
  work_id       uuid not null references works(id) on delete cascade,
  edition_id    uuid references editions(id) on delete set null,
  project_id    uuid not null references projects(id) on delete cascade,
  platform      text not null check (platform in ('amazon_corpus','hardcover')),
  external_id   text,
  rating        numeric(2,1),
  helpful_votes int,
  review_date   timestamptz,
  text          text,
  embedding     vector(384),
  aspect_cluster_id bigint,
  sentiment     numeric(4,3),
  processed     boolean not null default false,
  unique (platform, external_id)
);
create index reviews_work_idx on reviews (work_id);
create index reviews_embedding_idx on reviews using ivfflat (embedding vector_cosine_ops);

-- DISTILLED COMPLAINT CLUSTERS (the product of local NLP)
create table aspect_clusters (
  id             bigint generated always as identity primary key,
  project_id     uuid not null references projects(id) on delete cascade,
  work_id        uuid references works(id) on delete cascade,  -- null = niche-level
  bisac_code     text,
  label          text not null,                -- paraphrased aspect, e.g. 'outdated examples'
  member_count   int not null,
  reviewer_count int not null,                 -- distinct reviewers (agreement)
  helpful_weight numeric(6,3),
  platforms      text[] not null,              -- contributing platforms (credibility)
  cross_platform boolean not null default false,
  representative text                          -- short paraphrased summary, NOT a raw quote
);

-- DEMAND & SUPPLY SIGNALS (fresh, per BISAC)
create table demand_signals (
  id          bigint generated always as identity primary key,
  project_id  uuid not null references projects(id) on delete cascade,
  bisac_code  text not null,
  source      text not null check (source in ('nyt','googlebooks','hardcover')),
  metric      text not null,                    -- 'bestseller_weeks','ratings_count','read_count','review_velocity'
  value       numeric,
  as_of_date  date not null
);

create table supply_signals (
  id                 bigint generated always as identity primary key,
  project_id         uuid not null references projects(id) on delete cascade,
  bisac_code         text not null,
  source             text not null check (source in ('openlibrary','googlebooks')),
  title_count        int,
  recent_title_count int,                        -- post-cutoff titles (time-skew guard, §10)
  as_of_date         date not null
);

-- SCORES with mandatory validity/provenance columns
create table scores (
  id              bigint generated always as identity primary key,
  project_id      uuid not null references projects(id) on delete cascade,
  scope           text not null check (scope in ('work','bisac')),
  ref_id          text not null,
  demand_score    numeric(5,3),
  supply_scarcity numeric(5,3),
  unmet_need      numeric(5,3),
  gap_score       numeric(5,3),
  -- VALIDITY (mandatory):
  confidence      numeric(4,3) not null,
  sample_size     int not null,
  platforms_used  text[] not null,
  oldest_signal   date,
  newest_signal   date,
  incomplete      boolean not null default false, -- a layer failed/missing → withheld/imputed, never zeroed
  blind_spot      boolean not null default false, -- thin data → possible survivorship gap
  recent_supply_surge boolean not null default false, -- gap may be closing (§10)
  computed_at     timestamptz not null default now(),
  unique (project_id, scope, ref_id)
);

-- TAXONOMY: BISAC canonical spine + learned mappings + exception queue
create table taxonomy_crosswalk (
  id              bigint generated always as identity primary key,
  canonical_bisac text not null,
  source          text not null check (source in ('openlibrary','nyt','amazon','googlebooks')),
  source_label    text not null,
  confidence      numeric(3,2) not null default 1.0,
  origin          text not null check (origin in ('prebuilt','learned','manual')),
  unique (source, source_label)
);

create table unmapped_labels (
  id           bigint generated always as identity primary key,
  project_id   uuid not null references projects(id) on delete cascade,
  source       text not null,
  source_label text not null,
  occurrences  int not null default 1,
  resolved     boolean not null default false,
  unique (project_id, source, source_label)
);

-- OBSERVABILITY
create table analysis_runs (
  id           bigint generated always as identity primary key,
  project_id   uuid references projects(id) on delete cascade,
  mode         text not null check (mode in ('single_title','category_sweep','seed','validation')),
  target       text,
  sources_used text[],
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  status       text not null default 'running',  -- running | ok | partial | error
  counts       jsonb,
  error_detail text
);
```

---

## 6. Offline Seed Pipeline (`lacuna/seed/seed.py`)

Run once per project, locally. Heavy and slow by design — it pre-computes everything so interactive runs are fast. **All NLP here is local (§7); no external LLM call occurs in the seed.**

**6.1 Flow**
1. Load project config (target BISAC, subject filter, caps, pinned dataset + model + norm versions).
2. **Metadata pass:** stream `raw_meta_Books`, prefilter items to scope, build `editions` (extract ASIN/parent_asin/ISBN/format/price).
3. **Works grouping** (§6.3): collapse editions → `works`, assign `primary_bisac` via crosswalk.
4. **Review pass:** stream `raw_review_Books`; keep only **critical reviews (rating ≤ 3)** ranked by `helpful_votes`, capped per work (default 15). **Deliberately include the long tail** — sample low-review works too (§6.5).
5. **Embed** curated reviews locally (`all-MiniLM-L6-v2`); store `embedding`.
6. **Cluster** per work (and per BISAC for sweep) with HDBSCAN → `aspect_clusters`; **label each cluster locally** via zero-shot (`bart-large-mnli`) and store a **paraphrased** label + representative summary (never a raw quote). Record `reviewer_count`, `helpful_weight`, `platforms`.
7. **Upsert** distilled tables to Supabase (idempotent on the unique keys). Never write raw corpus text to the repo or version control.
8. Log an `analysis_runs` row with `mode='seed'`.

**6.2 Memory/scale:** use `streaming=True`; do joins/grouping in DuckDB/Polars locally, not in Supabase. Supabase receives only the distilled result.

**6.3 Works grouping rules** (`works_grouping.py`):
- Pass 1: group by shared `parent_asin`.
- Pass 2: group across parent_asins by `normalized_key = normalize(title)|normalize(author)` (lowercase, strip subtitle after `:`, strip format/series tokens, collapse punctuation/whitespace).
- Pass 3 tie-break: require title trigram similarity + exact author surname before merging; below threshold keep separate and flag.

**6.4 Re-seed determinism:** `normalize()` is **versioned** (`norm_version`). A version bump triggers a full rebuild of affected works (not in-place reconcile) so reviews never orphan. `seed.py` supports `--rebuild` and `--reconcile`.

**6.5 Long-tail selection:** book selection must include a configured share of low-review-count titles, or survivorship bias re-enters at ingestion. Never select books by popularity alone.

---

## 7. Local NLP / Aspect Extraction (`lacuna/nlp/`) — strictly zero-cost, strictly local

**No external LLM API for bulk tagging — ever.** This is a hard architectural boundary, not a preference. The pipeline is deterministic, free, and reproducible (pinned model revisions, §15). Raw review text never leaves the machine for an external API.

- `embeddings.py`: batch-embed review text with `all-MiniLM-L6-v2` on CPU. Cache by review hash.
- `clustering.py`: HDBSCAN over embeddings (per work for single-title; per BISAC for sweep), cosine space, to group complaints into aspect clusters.
- `aspects.py`: label each cluster locally via zero-shot classification (`bart-large-mnli`) against a configurable aspect taxonomy (`outdated`, `too_basic`, `too_advanced`, `poor_examples`, `inaccurate`, `badly_structured`, `overpriced`, `repetitive`, …), and produce a **paraphrased** cluster label + representative summary. No raw quotes are persisted or exported (ToU + token economy).
- The optional Anthropic step (§12) only ever receives the **already-aggregated clusters**, never raw reviews — so the system runs end-to-end at $0 with `ANTHROPIC_API_KEY` unset.

---

## 8. Fresh Ingestion & Per-Platform Normalization (`lacuna/adapters/`)

For a target work or niche, pull current data:
- **Hardcover:** GraphQL by ISBN/title → reviews, ratings distribution, read counts. Respect 60/min; paginate; back off on limit. Embed + cluster its reviews locally into `aspect_clusters` tagged `platform='hardcover'`.
- **NYT:** bestseller presence/weeks for the BISAC → `demand_signals`.
- **Google Books:** `ratingsCount` + category (BISAC anchor) → `demand_signals` + crosswalk learning.
- **Open Library:** subject title counts + recency → `supply_signals` (including `recent_title_count` for the time-skew guard).

Ratings are normalized **per platform** before any combination (each platform has its own rating culture — z-score or min-max within platform).

---

## 9. Cross-Platform Aggregation & Credibility (`lacuna/aggregation/cross_platform.py`)

The two sentiment-text platforms — the Amazon corpus (deep, historical) and Hardcover (fresh, live) — are aggregated into the same `aspect_clusters` space:
- Merge clusters across platforms by aspect-embedding similarity; when an aspect appears on more than one platform, set `cross_platform=true` and record the contributing `platforms`.
- **Cross-platform agreement is the credibility signal:** a complaint present on both Amazon and Hardcover is weighted more heavily and raises the score's `confidence`. A single-platform complaint is retained but flagged as such.
- Aggregation never blends raw per-platform ratings into a single average without the per-platform normalization in §8 — a naive blend across differing rating cultures is explicitly disallowed.
- `provenance.cross_platform_agreement_pct` (the share of a candidate's top complaints confirmed on >1 platform) is computed and surfaced in the export and dashboard.

---

## 10. Market-Gap Scoring (`lacuna/scoring/`) — resilient by construction

The score must preserve signal when a layer is weak and must **never collapse to zero because a single layer is missing or glitched**.

**Step order, per candidate (work or BISAC bucket):**

1. **Normalize** each component — `demand`, `supply_scarcity`, `unmet_need` — to [0,1] via **rank/percentile** normalization (outlier-robust; one mega-bestseller must not compress everything else toward zero).

2. **Missing-data rule (applied before any multiplication) — missing ≠ zero:**
   - A component whose underlying data **failed to fetch or is absent** is **never** treated as 0.
   - If **demand** is missing → **withhold** the score and set `incomplete=true` (demand is the gate; without it the score is not meaningful).
   - If only **supply_scarcity** or **unmet_need** is missing → **impute** it as the BISAC/category median and apply a `confidence` penalty; set `incomplete=true`.
   - A **genuine** zero (e.g. a truly saturated shelf → `supply_scarcity = 0`) is legitimate and is allowed to propagate. The rule distinguishes *absent data* (never zero) from *real zero* (propagates).

3. **Soft demand gate (dampen, never annihilate):**
   `demand_gate = max(epsilon, sigmoid(k * (demand - d0)))`, with `epsilon` defaulting to 0.05.
   A no-demand niche scores near-zero but **still appears, flagged** — it is never erased from view.

4. **Robust core via weighted geometric mean:**
   `core = (supply_scarcity^w_s * unmet_need^w_u)^(1 / (w_s + w_u))`
   The geometric mean keeps one weak-but-real layer from fully cancelling a strong one, while still going to zero only on a *genuine* zero (handled by step 2).

5. **Compose:** `gap_score = core * demand_gate` (both in [0,1]).

**Time-skew guard:** if `recent_title_count` shows a post-2023 surge of titles in the BISAC, set `recent_supply_surge=true` and down-weight — a gap with fresh books rushing in is a gap closing.

**Mandatory validity outputs** (written to `scores` and surfaced everywhere): `confidence` (driven by sample size, platform coverage, cross-platform agreement, and crosswalk mapping confidence), `sample_size`, `platforms_used`, `oldest_signal`/`newest_signal`, `incomplete`, `blind_spot`, `recent_supply_surge`.

---

## 11. Analysis Modes & Performance (`lacuna/pipeline/`)

**Single-Title Watchlist mode** (`single_title.py`): resolve the work(s) → pull fresh (Hardcover/Google Books) → merge with corpus clusters (§9) → score → export. Supports tracking a watchlist of specific ISBNs/titles. **First run ≈ 1–2 min**; re-run = seconds (cached). The robust, recommended path.

**Category Sweep mode** (`category_sweep.py`): iterate the niche's works → fuse at the **BISAC-bucket level** (not brittle per-book cross-source ISBN joins) → score per BISAC. **First run is bounded by Hardcover's 60/min**, so a large niche is **10–30+ min**; cached afterward. Surfaced in the UI as advanced / lower-confidence, but fully functional.

Heavy work is pre-computed and cached at ingest; interactive reads hit distilled Supabase tables, so the UI stays responsive.

---

## 12. LLM Context Pack Export (`lacuna/export/context_pack.py`)

The product the user feeds to their own LLM. **JSON + Markdown twin.** Compression comes from exporting **paraphrased aspect clusters**, never raw review text. Optional `ANTHROPIC_API_KEY` enables a local narrative draft; the pack is complete without it.

```json
{
  "legend": "gap_score 0-1, higher=more underserved. unmet_need is demand-gated (soft). Every score carries confidence + provenance.",
  "instructions_to_model": [
    "Treat each candidate as a HYPOTHESIS, not a finding.",
    "Do NOT infer demand from dissatisfaction alone; demand must come from the demand fields.",
    "For each candidate state: strongest case FOR, strongest case AGAINST, and what live Amazon data would confirm or kill it.",
    "Down-weight candidates with confidence < 0.5, incomplete=true, recent_supply_surge=true, or newest_signal older than 18 months.",
    "Name what is NOT in this data: post-2023 trends, true greenfield gaps, actual unit sales."
  ],
  "known_limitations": [
    "Deep sentiment corpus ends 2023-09; US amazon.com / English only.",
    "Fresh layer (Hardcover) has thinner volume than Amazon; some titles carry little signal.",
    "Demand is a popularity PROXY, not unit sales or BSR.",
    "Survivorship: unwritten books leave no trace — thin data may be a blind spot, not an opportunity.",
    "Ratings are dissatisfaction signals, not willingness-to-pay."
  ],
  "target": { "project": "string", "bisac": ["..."], "mode": "single_title|category_sweep" },
  "generated_at": "ISO",
  "provenance": {
    "platforms_used": ["amazon_corpus","hardcover"],
    "as_of": { "sentiment_deep": "2023-09", "sentiment_fresh": "2026-06", "demand": "2026-06", "supply": "2026-06" },
    "total_reviews": 0, "cross_platform_agreement_pct": 0.0
  },
  "candidates": [
    {
      "ref": "work or bisac",
      "title_or_subject": "string",
      "gap_score": 0.0,
      "components": { "demand": 0.0, "supply_scarcity": 0.0, "unmet_need": 0.0 },
      "validity": {
        "confidence": 0.0, "sample_size": 0, "platforms": ["..."],
        "oldest_signal": "ISO", "newest_signal": "ISO",
        "incomplete": false, "blind_spot": false, "recent_supply_surge": false
      },
      "top_complaints": [
        { "aspect": "outdated examples", "reviewer_count": 0, "helpful_weight": 0.0, "platforms": ["amazon_corpus","hardcover"], "cross_platform": true }
      ],
      "demand_evidence": { "nyt_weeks": 0, "ratings_count": 0, "read_count": 0, "review_velocity_per_mo": 0.0 }
    }
  ]
}
```
**Markdown twin:** same content, compact, a one-line legend, a `> Treat as hypotheses` banner, the limitations block, bulleted candidates. Honors a `token_budget` (default ~4k) that caps candidates and complaint clusters so it pastes cold into any model.

---

## 13. Configuration — Two Tiers (`config/`)

**`default.yaml` — INTENT knobs (exposed, user-editable; preferences, no correct answer):**
```yaml
project_name: "Example - Stoic Self-Help"
target_bisac: ["SEL036000", "PHI011000"]      # change this to retarget
subject_filter: { keywords: ["stoicism", "discipline"] }
timely_vs_evergreen: 0.5                        # 0=evergreen depth, 1=fresh
recency_window_months: 12
export: { max_candidates: 15, token_budget: 4000 }
```

**`advanced.yaml` — CORRECTNESS knobs (locked defaults, warned, rarely touched):**
```yaml
# WARNING: these are statistical validity controls. Changing them can make the
# tool produce confidently-wrong results. Defaults are tuned; edit only if you
# understand the consequence stated on each line.
min_sample_gate: 20            # below this, ratings are untrusted (small-sample noise)
bayes_shrinkage_strength: 15   # pull small-n ratings toward the category mean
demand_gate_floor_epsilon: 0.05
demand_gate_steepness_k: 8
demand_gate_midpoint_d0: 0.4
geomean_weight_supply: 1.0
geomean_weight_unmet: 1.0
normalization: "rank"          # rank/percentile = outlier-robust
crosswalk_auto_accept: 0.85    # cosine >= this -> auto-map; below 0.55 -> auto-reject
curated_reviews_per_work: 15
longtail_share: 0.3            # min fraction of low-review works to include

# Model + dataset revisions are RESOLVED, VALIDATED, and PINNED by the build agent
# at build time (see section 15). The build writes the verified hashes here; they
# must never ship as placeholder text.
models:
  embedding:  { name: "sentence-transformers/all-MiniLM-L6-v2", revision: "<resolved-at-build>" }
  zero_shot:  { name: "facebook/bart-large-mnli",               revision: "<resolved-at-build>" }
dataset:
  amazon_reviews: { name: "McAuley-Lab/Amazon-Reviews-2023", revision: "<resolved-at-build>" }
```

---

## 14. Dashboard & CLI (`app/`)

**CLI (`cli.py`, Typer):**
- `lacuna validate-hardcover` — the early validation gate (§18): fetch a real title, confirm live review availability.
- `lacuna seed` — run the offline seed for the configured project.
- `lacuna analyze --isbn <isbn>` / `--title <t>` — Single-Title Watchlist analysis → prints summary + writes Context Pack.
- `lacuna sweep` — Category Sweep for the project.
- `lacuna export --out pack.json` — (re)generate the Context Pack.

**Streamlit dashboard (`streamlit_app.py`):**
- **Project switcher** (workspaces).
- **Single-Title Watchlist view:** input/track ISBNs/titles → run → clustered complaints (aspect, reviewer_count, helpful_weight, platform badges, cross-platform flag), rating distribution, demand evidence, and a **provenance line on every panel** ("N reviews · platforms · date range · confidence"). Download Context Pack (JSON + MD).
- **Category Sweep view:** ranked gap candidates with `confidence`, `blind_spot`, and `recent_supply_surge` shown inline; advanced-mode banner.
- **Timely↔evergreen slider** with a **freshness indicator that dims** as it moves toward "timely" (honest signal that the fresh layer is thinner).
- Every control is wired to live queries; empty/loading/error states implemented; no dead ends.

---

## 15. Resilience, Maintenance & Build-Time Revision Pinning

- **Dynamic revision pinning (mandatory, build-time):** the build agent must **resolve, validate, and pin** the exact current Hugging Face revisions for the dataset (`McAuley-Lab/Amazon-Reviews-2023`) and both models (`sentence-transformers/all-MiniLM-L6-v2`, `facebook/bart-large-mnli`). It queries the Hub for the current commit hashes, verifies they load, writes the verified hashes into `config/advanced.yaml` and the lockfile, and **fails the build loudly** if any cannot be resolved or verified. No placeholder text (`PINNED`, `<resolved-at-build>`, etc.) may remain in a shipped build.
- **Adapters isolate every external contract.** Swapping a source or mirror is a one-file change.
- **Boundary validation:** pydantic models on every API/dataset response — a shape change fails loud with a clear message, never silently corrupts scores.
- **Pinning of dependencies + environment:** `uv.lock` committed; pinned dataset/model revisions; Supabase is the managed database (no environment to reproduce locally beyond the Python venv).
- **Contract tests** (`tests/`): a recorded sample response per source + a parser test, so a fork's CI catches drift early. Includes the Hardcover live-availability check.
- **Backoff + circuit breaker** per adapter; a degraded source is skipped and logged in `analysis_runs`, never cascades.
- **Fail-loud principle:** every external dependency is assumed to eventually break; it must break with a documented swap path, not silent bad output.

---

## 16. Documentation Requirements

- **`README.md`:** the click-by-click setup — create the Supabase project + set a password; enable the `pgvector` extension; copy the **Session Pooler** connection string (not Direct) and replace the password placeholder; obtain the Hardcover token (strip the `Bearer ` prefix), Google Books key, and NYT key; `cp .env.example .env` and fill; `uv sync`; `uv run alembic upgrade head`; `uv run lacuna validate-hardcover`; `uv run lacuna seed`; `uv run streamlit run app/streamlit_app.py`. State the 60/min and corpus-cutoff realities and the Supabase free-tier pause plainly. How to retarget a niche: edit `config/default.yaml`.
- **`docs/METHODOLOGY.md`:** the scoring model (rank normalization, missing≠zero, soft demand gate, weighted geometric mean), cross-platform normalization and agreement, in the builder's own words.
- **`docs/LIMITATIONS.md`:** time-skew, survivorship, dissatisfaction-≠-demand, demand-is-a-proxy, per-book volume variance, platform biases, and the legal mosaic (Amazon Customer Reviews ToU — ship the fetch script, never redistribute the text; Hardcover developer guidelines). Write it bluntly — this is the credibility document.

---

## 17. Acceptance Criteria (definition of done)

1. With `.env` filled (Supabase Session Pooler URL + three keys) and `pgvector` enabled on the project, `uv run alembic upgrade head` provisions the full schema on Supabase. No Docker or local Postgres is referenced anywhere.
2. `uv run lacuna validate-hardcover` **passes the early gate** — it fetches a real title via the Hardcover API and confirms live review availability — and the build sequence requires this to pass **before** the fusion/scoring layers are exercised (§18).
3. `uv run lacuna seed` populates a project's distilled tables from the real McAuley corpus, with all aspect tagging done by **local NLP** and **zero** raw-corpus files committed.
4. The build agent has **resolved, validated, and pinned** the real Hugging Face dataset and model (`all-MiniLM-L6-v2`, `bart-large-mnli`) revisions into config + lockfile; **no placeholder revision text remains**, and the build fails loudly if any revision is unverifiable.
5. The app runs end-to-end with `ANTHROPIC_API_KEY` unset — no raw review text is ever sent to an external LLM API; runtime cost is $0.
6. `lacuna analyze --isbn <isbn>` returns, in ≤ ~2 min on first run, clustered complaints with provenance and a valid Context Pack (JSON + MD).
7. Fresh Hardcover data is normalized per platform and aggregated with corpus clusters; cross-platform agreement is reflected in `confidence` and surfaced as `cross_platform_agreement_pct`.
8. Scoring **never computes a failed/missing layer as 0** (`incomplete` set, value withheld or median-imputed with a confidence penalty); a genuine zero still propagates; thin data sets `blind_spot`; a post-2023 supply surge sets `recent_supply_surge`. The core uses a weighted geometric mean with a soft, epsilon-floored demand gate.
9. **Both modes ship and run:** Single-Title Watchlist (fast) and Category Sweep (BISAC-bucket fusion, flagged advanced).
10. Two projects (two niches) coexist with fully isolated data via `project_id`.
11. Every dashboard panel shows provenance; the timely↔evergreen slider shows a dimming freshness indicator; no placeholder dead ends.
12. No Reddit code, schema enum, adapter, config flag, or workstream exists anywhere in the repository.
13. Contract tests pass (including the Hardcover live-availability check); `uv.lock` and pinned dataset/model revisions are present.

---

## 18. Subagent Workstreams & Build Sequence

Parallelizable streams (dependencies in brackets). **The early validation gate (G0) is a hard checkpoint: the historical fusion and scoring layers (F, G, H) must not be built or run until G0 passes.**

- **A — Infra:** `pyproject`/`uv.lock`, `config.py` (env load + `DATABASE_URL` driver-scheme normalization), `.env.example`, alembic migrations for §5 (schema + `pgvector`). Resolve + validate + pin dataset/model revisions (§15). *(none)*
- **B — Adapters:** Hardcover, Google Books, NYT, Open Library, corpus clients + pydantic schemas + backoff. *(A)*
- **G0 — EARLY VALIDATION GATE:** implement `lacuna validate-hardcover`; fetch a real title via the Hardcover API and verify live review availability; log to `analysis_runs (mode='validation')`. **Must pass before F, G, H proceed.** *(A, B — specifically the Hardcover adapter)*
- **C — Seed & works grouping:** `seed.py`, `works_grouping.py`, versioned `normalization.py`, long-tail selection. *(A, B)*
- **D — Local NLP:** embeddings, HDBSCAN clustering, local zero-shot aspect labeling, cluster persistence — strictly local, no external LLM. *(A, C)*
- **E — Taxonomy:** BISAC spine, crosswalk learning (Google-Books-anchored), unmapped queue. *(A, B)*
- **F — Scoring:** rank normalization, missing≠zero handling, soft demand gate, weighted geometric mean, time-skew guard, validity outputs. *(D, E, G0)*
- **G — Aggregation:** per-platform normalization + cross-platform cluster merge + agreement metric. *(B, D, G0)*
- **H — Export:** Context Pack JSON + Markdown, hypothesis scaffolding, optional local narrative. *(F, G, G0)*
- **I — Interface:** Typer CLI + Streamlit dashboard with provenance + freshness indicator + both modes. *(F, G, H)*
- **J — Docs & tests:** README (Supabase click-by-click), METHODOLOGY, LIMITATIONS, contract tests incl. Hardcover live-availability. *(all)*

**Sequence:** A → B → **G0 (gate)** → (C, E in parallel) → D → (F, G in parallel) → H → I → J.

---

*The validity controls in §10, the strictly-local NLP boundary in §7, the build-time revision pinning in §15, and the early Hardcover gate in §18 are not optional polish — they are load-bearing. Implement them as specified.*
