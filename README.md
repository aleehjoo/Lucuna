# Lacuna

A local, $0-runtime engine that surfaces evidence-backed hypotheses about reader dissatisfaction in a target book niche. It aggregates real review sentiment across platforms, gates it against demand, and exports an LLM-ready Context Pack you feed into your own model.

All bulk text analysis runs locally (MiniLM embeddings + HDBSCAN clustering + BART zero-shot labeling). No raw review text is sent to any external LLM API. The tool runs end-to-end with `ANTHROPIC_API_KEY` unset.

---

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (if `uv` is not on your PATH, substitute `python -m uv` for every `uv` command below)
- A Supabase account (free tier is sufficient to start)
- API keys for Hardcover, Google Books, and NYT Books (all have free tiers)

---

## Step 1 — Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in.
2. Click **New project**. Give it a name and set a **database password** — save this password, you will need it in a moment.
3. Wait for the project to finish provisioning (about 30–60 seconds).

### Enable pgvector

4. In the Supabase dashboard, go to **Database → Extensions**.
5. Search for `vector` and enable the **`vector`** extension. This is required — the schema migration will fail without it.

### Copy the Session Pooler connection string

6. In the dashboard, click **Connect** (top bar).
7. Select the **Session pooler** tab. Copy the connection string. It looks like:
   ```
   postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```
8. **Do not use the Direct connection string** — it is IPv6-only on the free tier and will fail on most home networks.
9. Replace `<password>` in the string with the database password you set in step 2.

---

## Step 2 — Get API Keys

### Hardcover token

1. Sign in at [hardcover.app](https://hardcover.app) and go to **Account → API**.
2. Copy the token. It starts with `eyJ...`.
3. **Strip the `Bearer ` prefix** — paste only the token itself into `.env`.
4. Tokens expire yearly; if you see authentication errors, regenerate here.

### Google Books API key

1. Go to [Google Cloud Console](https://console.cloud.google.com).
2. Create a project (or use an existing one).
3. Navigate to **APIs & Services → Library**, search for **Books API**, and enable it.
4. Go to **APIs & Services → Credentials**, click **Create credentials → API key**.
5. Copy the key.

### NYT Books API key

1. Go to [developer.nytimes.com](https://developer.nytimes.com).
2. Create an account, then go to **Apps → New App**.
3. Enable the **Books API** for the app.
4. Copy the API key.

---

## Step 3 — Configure `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in the values:

```bash
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
HARDCOVER_API_TOKEN=eyJ...          # the token without "Bearer "
GOOGLE_BOOKS_API_KEY=AIza...
NYT_BOOKS_API_KEY=...
ANTHROPIC_API_KEY=                  # optional — leave blank to run at $0
```

`.env` is excluded from version control via `.gitignore`. Never commit it.

---

## Step 4 — Install Dependencies

```bash
uv sync
```

This installs all dependencies from `uv.lock` into a local virtual environment.

---

## Step 5 — Pin Model and Dataset Revisions

```bash
uv run python -m scripts.pin_revisions
```

This resolves and validates the current Hugging Face commit hashes for the embedding model (`all-MiniLM-L6-v2`), the zero-shot model (`facebook/bart-large-mnli`), and the Amazon Reviews dataset, then writes the verified hashes into `config/advanced.yaml`. The build fails loudly if any revision cannot be verified. No placeholder hashes ship.

---

## Step 6 — Run Database Migrations

```bash
uv run alembic upgrade head
```

This provisions the full schema on your Supabase project, including enabling the `pgvector` extension at the SQL level. Requires `DATABASE_URL` in `.env` and the `vector` extension toggled on in the dashboard (Step 1).

---

## Step 7 — Validate Hardcover Connectivity

```bash
uv run lacuna validate-hardcover
```

This is a hard gate. It fetches a real title via the Hardcover API and confirms that live reviews are available. The scoring and aggregation layers must not be run until this passes. If it fails, check your `HARDCOVER_API_TOKEN`.

---

## Step 8 — Seed the Database

```bash
uv run lacuna seed
```

This runs the offline seed pipeline: streams the Amazon Reviews corpus, embeds and clusters critical reviews locally, and writes distilled aspect clusters to your Supabase project. No raw review text is committed or exported. This is a slow one-time step — expect 20–60+ minutes depending on niche size and your machine. Subsequent runs are fast (cached).

**Bounded scan:** the seed streams a bounded slice of the corpus (defaults: `--meta-limit 200000 --review-limit 1000000 --max-works 60`, all overridable). Niche subjects surface fewer works under a bounded scan — raise the limits for fuller coverage. Coverage is recorded in `analysis_runs.counts`.

---

## Step 8b — Score & Export the Context Pack

```bash
uv run lacuna sweep      # category sweep over seeded works -> ranked Context Pack
uv run lacuna export     # (re)generate the pack from the latest seeded data
```

Both run at **$0** with no external keys: they read the seeded works + aspect clusters, score the cohort (missing demand/supply layers are *withheld*, not zeroed — candidates are flagged `incomplete`), and write `pack.json` + `pack.md`. The single-title fresh-pull path needs a live token:

```bash
uv run lacuna analyze --isbn <isbn>    # needs HARDCOVER_API_TOKEN in .env (fresh Hardcover pull)
```

---

## Step 9 — Launch the Dashboard

```bash
uv run streamlit run app/streamlit_app.py
```

Opens the Streamlit dashboard in your browser. From here you can run Single-Title Watchlist analysis, Category Sweep, and download the Context Pack (JSON + Markdown).

---

## Realities to Know Before You Run

**Hardcover rate limit:** 60 requests per minute. The adapter enforces this, but a large Category Sweep will be slow — expect 10–30+ minutes on first run. Cached afterward.

**Corpus cutoff:** the deep Amazon sentiment layer ends September 2023, US english only. See `docs/LIMITATIONS.md`.

**Supabase free tier:** Supabase pauses free-tier projects after a period of inactivity (currently one week). If you see connection errors after a break, go to the Supabase dashboard and restore the project.

**$0 runtime:** the tool runs end-to-end with `ANTHROPIC_API_KEY` unset. The optional Anthropic call (narrative draft in the export) is the only part that costs money, and only if you set the key and trigger it explicitly.

---

## Retargeting a Niche

Edit `config/default.yaml` and update `target_bisac`, `project_name`, and `subject_filter`. Then re-run `lacuna seed` for the new project. Two projects (two niches) coexist with fully isolated data via `project_id` in the database.

```yaml
project_name: "Example — Stoic Self-Help"
target_bisac: ["SEL036000", "PHI011000"]
subject_filter:
  keywords: ["stoicism", "discipline"]
```

---

## Further Reading

- `docs/METHODOLOGY.md` — the scoring model in detail: rank normalization, missing≠zero, soft demand gate, weighted geometric mean, confidence formula, cross-platform aggregation.
- `docs/LIMITATIONS.md` — blunt credibility document: corpus cutoff, survivorship bias, demand proxies, legal mosaic.
- `config/advanced.yaml` — correctness knobs with inline warnings. Change only if you understand the consequence.
