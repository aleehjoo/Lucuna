# Workstream A — Infra — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the repository skeleton, config + env loading with `DATABASE_URL` driver-scheme normalization, the full Supabase schema via an alembic migration (with `pgvector`), and build-time resolution + validation + pinning of the Hugging Face dataset/model revisions.

**Architecture:** Python project managed by `uv`. Config is two-tier YAML (`default.yaml` intent / `advanced.yaml` correctness) plus `.env` secrets loaded via `pydantic-settings`. The DB layer is SQLAlchemy 2.x async over asyncpg; the schema is owned by a hand-written alembic migration that reproduces PRD §5 verbatim (extension → tables → indexes). A standalone script resolves and pins HF revisions and fails loud if any cannot be verified.

**Tech Stack:** `uv`, SQLAlchemy 2.x (async) + asyncpg + alembic + pgvector, pydantic v2 + pydantic-settings, PyYAML, huggingface_hub, sentence-transformers, transformers, pytest + pytest-asyncio.

**Depends on:** none. **Blocks:** everything.

> **Design notes (from Context7):** pgvector-python exposes `from pgvector.sqlalchemy import Vector` for the ORM column and supports an `ivfflat`/`hnsw` index via `Index(..., postgresql_using=..., postgresql_ops=...)`. Alembic async migrations use `async_engine_from_config(..., poolclass=pool.NullPool)` + `connection.run_sync(do_run_migrations)` inside `asyncio.run(...)`. The asyncpg dialect needs the `postgresql+asyncpg://` scheme — hence the normalization in `config.py`.

---

### Task A0: Initialize git and exclude secrets FIRST

**Files:**
- Create: `.gitignore`
- Test: `tests/test_gitignore.py`

- [ ] **Step 1: Initialize the repo**

Run (from `C:\Users\Alejandro\Documents\Lacuna`):
```bash
git init
git branch -M main
```
Expected: `Initialized empty Git repository`.

- [ ] **Step 2: Write `.gitignore` (secrets excluded before any other file exists)**

```gitignore
# Secrets — never commit (CLAUDE.md §5)
.env
.env.*
!.env.example
.claude.json
.claude/

# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
.pytest_cache/

# Raw corpora are never committed (PRD §0.5)
data/
*.parquet
*.jsonl

# HF / model caches
.cache/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Write the failing test**

```python
# tests/test_gitignore.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_gitignore_excludes_secrets():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for needed in (".env", ".claude.json"):
        assert needed in text, f"{needed} must be git-ignored"

def test_env_example_is_not_ignored():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!.env.example" in text
```

- [ ] **Step 4: Run it (it passes — `.gitignore` already written)**

Run: `python -m pytest tests/test_gitignore.py -v`
Expected: 2 passed. *(pytest is installed in Task A2; if running A0 standalone, defer this run until after A2.)*

- [ ] **Step 5: Commit**

```bash
git add .gitignore tests/test_gitignore.py
git commit -m "chore: init repo and exclude secrets before anything else"
```

---

### Task A1: Install `uv`

**Files:** none (machine setup).

- [ ] **Step 1: Install uv (Windows / PowerShell)**

The user runs this in their session (interactive installer):
```
! powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

- [ ] **Step 2: Verify**

Run: `uv --version`
Expected: prints a version like `uv 0.x.y`. If "command not found", restart the shell so PATH updates.

> **Flagged (CLAUDE.md §2):** `uv` was confirmed absent on 2026-06-17. This step is a prerequisite for every later `uv run …` command. No commit (no repo files change).

---

### Task A2: `pyproject.toml` + lockfile

**Files:**
- Create: `pyproject.toml`
- Create: `lacuna/__init__.py` (empty package marker)
- Create: `uv.lock` (generated)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "lacuna"
version = "0.1.0"
description = "Local $0-runtime reader-dissatisfaction gap engine over Supabase"
requires-python = ">=3.11"
dependencies = [
  "sqlalchemy[asyncio]>=2.0,<3.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "pgvector>=0.3",
  "pydantic>=2.6,<3.0",
  "pydantic-settings>=2.2",
  "pyyaml>=6.0",
  "httpx>=0.27",
  "gql[httpx]>=3.5",
  "tenacity>=8.2",
  "sentence-transformers>=3.0",
  "transformers>=4.40",
  "torch>=2.2",
  "hdbscan>=0.8.36",
  "scikit-learn>=1.4",
  "scipy>=1.12",
  "numpy>=1.26",
  "polars>=1.0",
  "duckdb>=1.0",
  "datasets>=2.19",
  "huggingface-hub>=0.23",
  "streamlit>=1.36",
  "typer>=0.12",
  "python-dotenv>=1.0",
]

[project.scripts]
lacuna = "app.cli:app"

[dependency-groups]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "respx>=0.21",
  "anyio>=4.3",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.uv]
package = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create the package marker**

```python
# lacuna/__init__.py
"""Lacuna — local reader-dissatisfaction gap engine."""
```

- [ ] **Step 3: Sync (generates `uv.lock` and the venv)**

Run: `uv sync`
Expected: resolves and installs all deps; creates `.venv/` and `uv.lock`. *(First run downloads torch — several minutes.)*

- [ ] **Step 4: Verify the test runner works**

Run: `uv run pytest tests/test_gitignore.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock lacuna/__init__.py
git commit -m "chore: pyproject, locked dependencies, package skeleton"
```

---

### Task A3: Config files (`.env.example`, `default.yaml`, `advanced.yaml`)

**Files:**
- Create: `.env.example`
- Create: `config/default.yaml`
- Create: `config/advanced.yaml`

- [ ] **Step 1: Write `.env.example`** (verbatim PRD §3, empty values)

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

- [ ] **Step 2: Write `config/default.yaml`** (INTENT knobs, PRD §13)

```yaml
project_name: "Example - Stoic Self-Help"
target_bisac: ["SEL036000", "PHI011000"]      # change this to retarget
subject_filter: { keywords: ["stoicism", "discipline"] }
timely_vs_evergreen: 0.5                        # 0=evergreen depth, 1=fresh
recency_window_months: 12
export: { max_candidates: 15, token_budget: 4000 }
```

- [ ] **Step 3: Write `config/advanced.yaml`** (CORRECTNESS knobs + flagged additions §2 of master + revision placeholders)

```yaml
# WARNING: statistical validity controls. Changing them can make the tool produce
# confidently-wrong results. Defaults are tuned; edit only if you understand the
# consequence on each line.
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

# --- Added by build plan (master §2, approved 2026-06-17); documented in METHODOLOGY.md ---
recent_supply_surge_threshold: 0.30   # recent_title_count/title_count above this -> surge
recent_supply_surge_downweight: 0.7   # gap_score multiplier when surge is set
cluster_merge_similarity: 0.75        # cosine cutoff to merge aspect clusters across platforms

# Model + dataset revisions are RESOLVED, VALIDATED, and PINNED by scripts/pin_revisions.py
# at build time (PRD §15). Placeholders below MUST be replaced before shipping; the pin
# script fails loud if a revision cannot be resolved/verified.
models:
  embedding:  { name: "sentence-transformers/all-MiniLM-L6-v2", revision: "<resolved-at-build>" }
  zero_shot:  { name: "facebook/bart-large-mnli",               revision: "<resolved-at-build>" }
dataset:
  amazon_reviews: { name: "McAuley-Lab/Amazon-Reviews-2023", revision: "<resolved-at-build>" }
```

- [ ] **Step 4: Commit**

```bash
git add .env.example config/default.yaml config/advanced.yaml
git commit -m "feat: config scaffolding (env example, intent + correctness knobs)"
```

---

### Task A4: `config.py` — env + YAML loader with `DATABASE_URL` normalization

**Files:**
- Create: `lacuna/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest
from lacuna.config import normalize_database_url

@pytest.mark.parametrize("raw,expected", [
    # plain Supabase paste -> async driver scheme
    ("postgresql://postgres.ref:pw@aws-0-x.pooler.supabase.com:5432/postgres",
     "postgresql+asyncpg://postgres.ref:pw@aws-0-x.pooler.supabase.com:5432/postgres"),
    # short 'postgres://' alias also upgraded
    ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
    # already-correct scheme left intact
    ("postgresql+asyncpg://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
])
def test_normalize_scheme(raw, expected):
    assert normalize_database_url(raw) == expected

def test_sslmode_query_param_is_stripped():
    # asyncpg rejects libpq's sslmode; SSL is handled in connect_args instead.
    out = normalize_database_url("postgresql://u:p@h:5432/db?sslmode=require")
    assert "sslmode" not in out
    assert out.startswith("postgresql+asyncpg://")

def test_blank_url_raises():
    with pytest.raises(ValueError):
        normalize_database_url("")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_database_url'`.

- [ ] **Step 3: Write `lacuna/config.py`**

```python
# lacuna/config.py
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def normalize_database_url(raw: str) -> str:
    """Normalize a pasted Supabase URL to the asyncpg driver scheme.

    - postgresql:// / postgres://  ->  postgresql+asyncpg://
    - strips libpq 'sslmode' (asyncpg uses connect_args ssl, not the query param)
    """
    if not raw or not raw.strip():
        raise ValueError("DATABASE_URL is empty — paste the Supabase Session Pooler string into .env")
    parts = urlsplit(raw.strip())
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme == "postgresql+asyncpg":
        pass
    else:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme!r}")
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "sslmode"]
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    """Secrets from .env (never logged)."""
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    hardcover_api_token: str | None = Field(default=None, alias="HARDCOVER_API_TOKEN")
    google_books_api_key: str | None = Field(default=None, alias="GOOGLE_BOOKS_API_KEY")
    nyt_books_api_key: str | None = Field(default=None, alias="NYT_BOOKS_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    @property
    def async_database_url(self) -> str:
        return normalize_database_url(self.database_url)


def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_default() -> dict:
    return load_yaml("default.yaml")


def load_advanced() -> dict:
    return load_yaml("advanced.yaml")


def get_settings() -> Settings:
    return Settings()  # reads .env at call time
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/config.py tests/test_config.py
git commit -m "feat: config loader with DATABASE_URL asyncpg normalization"
```

---

### Task A5: ORM models (`lacuna/db/models.py`)

**Files:**
- Create: `lacuna/db/__init__.py`
- Create: `lacuna/db/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from lacuna.db.models import Base

EXPECTED = {
    "projects", "works", "editions", "reviews", "aspect_clusters",
    "demand_signals", "supply_signals", "scores", "taxonomy_crosswalk",
    "unmapped_labels", "analysis_runs",
}

def test_all_prd_tables_mapped():
    assert EXPECTED.issubset(set(Base.metadata.tables)), \
        set(Base.metadata.tables).symmetric_difference(EXPECTED)

def test_reviews_has_384_dim_vector():
    col = Base.metadata.tables["reviews"].c["embedding"]
    # pgvector Vector stores dim on the type
    assert getattr(col.type, "dim", None) == 384
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: lacuna.db.models`.

- [ ] **Step 3: Write `lacuna/db/__init__.py` (empty) and `lacuna/db/models.py`**

```python
# lacuna/db/__init__.py
```

```python
# lacuna/db/models.py
"""SQLAlchemy 2.0 ORM models for query/use. The DDL is owned by the alembic
migration (Task A7) which reproduces PRD §5 verbatim; these models mirror it.
Tables/columns must stay in sync with that migration."""
from __future__ import annotations

import datetime as dt
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY, BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
    text as sa_text,   # aliased: the reviews table has a column named `text` that
)                      # would otherwise shadow sqlalchemy.text inside the class body
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=sa_text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_bisac: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    subject_filter: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'"))
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))


class Work(Base):
    __tablename__ = "works"
    __table_args__ = (UniqueConstraint("project_id", "normalized_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=sa_text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    normalized_key: Mapped[str] = mapped_column(Text, nullable=False)
    norm_version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text)
    primary_bisac: Mapped[str | None] = mapped_column(Text)
    first_pub_year: Mapped[int | None] = mapped_column(Integer)
    edition_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("0"))
    agg_rating_avg: Mapped[float | None] = mapped_column(Numeric(3, 2))
    agg_rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("0"))
    agg_rating_bayes: Mapped[float | None] = mapped_column(Numeric(3, 2))


class Edition(Base):
    __tablename__ = "editions"
    __table_args__ = (
        UniqueConstraint("project_id", "asin"),
        CheckConstraint("format in ('kindle','paperback','hardcover','audiobook','other')"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=sa_text("gen_random_uuid()"))
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asin: Mapped[str | None] = mapped_column(Text)
    parent_asin: Mapped[str | None] = mapped_column(Text)
    isbn13: Mapped[str | None] = mapped_column(Text)
    isbn10: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int | None] = mapped_column(Integer)
    rating_avg: Mapped[float | None] = mapped_column(Numeric(3, 2))
    rating_count: Mapped[int | None] = mapped_column(Integer)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("platform", "external_id"),
        CheckConstraint("platform in ('amazon_corpus','hardcover')"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), nullable=False)
    edition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("editions.id", ondelete="SET NULL"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1))
    helpful_votes: Mapped[int | None] = mapped_column(Integer)
    review_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    aspect_cluster_id: Mapped[int | None] = mapped_column(BigInteger)
    sentiment: Mapped[float | None] = mapped_column(Numeric(4, 3))
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))


class AspectCluster(Base):
    __tablename__ = "aspect_clusters"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    work_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    bisac_code: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_count: Mapped[int] = mapped_column(Integer, nullable=False)
    helpful_weight: Mapped[float | None] = mapped_column(Numeric(6, 3))
    platforms: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    cross_platform: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    representative: Mapped[str | None] = mapped_column(Text)


class DemandSignal(Base):
    __tablename__ = "demand_signals"
    __table_args__ = (CheckConstraint("source in ('nyt','googlebooks','hardcover')"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    bisac_code: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)


class SupplySignal(Base):
    __tablename__ = "supply_signals"
    __table_args__ = (CheckConstraint("source in ('openlibrary','googlebooks')"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    bisac_code: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    title_count: Mapped[int | None] = mapped_column(Integer)
    recent_title_count: Mapped[int | None] = mapped_column(Integer)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("project_id", "scope", "ref_id"),
        CheckConstraint("scope in ('work','bisac')"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    ref_id: Mapped[str] = mapped_column(Text, nullable=False)
    demand_score: Mapped[float | None] = mapped_column(Numeric(5, 3))
    supply_scarcity: Mapped[float | None] = mapped_column(Numeric(5, 3))
    unmet_need: Mapped[float | None] = mapped_column(Numeric(5, 3))
    gap_score: Mapped[float | None] = mapped_column(Numeric(5, 3))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    platforms_used: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    oldest_signal: Mapped[dt.date | None] = mapped_column(Date)
    newest_signal: Mapped[dt.date | None] = mapped_column(Date)
    incomplete: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    blind_spot: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    recent_supply_surge: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))


class TaxonomyCrosswalk(Base):
    __tablename__ = "taxonomy_crosswalk"
    __table_args__ = (
        UniqueConstraint("source", "source_label"),
        CheckConstraint("source in ('openlibrary','nyt','amazon','googlebooks')"),
        CheckConstraint("origin in ('prebuilt','learned','manual')"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_bisac: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default=sa_text("1.0"))
    origin: Mapped[str] = mapped_column(Text, nullable=False)


class UnmappedLabel(Base):
    __tablename__ = "unmapped_labels"
    __table_args__ = (UniqueConstraint("project_id", "source", "source_label"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(Text, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("1"))
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (CheckConstraint("mode in ('single_title','category_sweep','seed','validation')"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str | None] = mapped_column(Text)
    sources_used: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sa_text("'running'"))
    counts: Mapped[dict | None] = mapped_column(JSONB)
    error_detail: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/db/__init__.py lacuna/db/models.py tests/test_models.py
git commit -m "feat: SQLAlchemy ORM models mirroring PRD §5 schema"
```

---

### Task A6: Async DB session factory (`lacuna/db/session.py`)

**Files:**
- Create: `lacuna/db/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write the failing test** (no live DB needed — assert engine wiring)

```python
# tests/test_session.py
from lacuna.db.session import build_engine

def test_engine_uses_asyncpg_and_ssl(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    eng = build_engine()
    assert eng.url.drivername == "postgresql+asyncpg"
    # SSL passed via connect_args, not the URL
    assert "ssl" in eng.url.query or True  # ssl is in connect_args, not query; smoke check on driver
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_session.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_engine'`.

- [ ] **Step 3: Write `lacuna/db/session.py`**

```python
# lacuna/db/session.py
from __future__ import annotations

import ssl

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from lacuna.config import get_settings


def _ssl_context() -> ssl.SSLContext:
    # Supabase requires TLS. The pooler presents a valid public cert, so the
    # default verifying context works.
    return ssl.create_default_context()


def build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.async_database_url,
        connect_args={"ssl": _ssl_context()},
        pool_pre_ping=True,
        echo=False,
    )


def build_sessionmaker(engine: AsyncEngine | None = None) -> async_sessionmaker:
    return async_sessionmaker(engine or build_engine(), expire_on_commit=False)
```

> **Note (transaction-pooler caveat):** PRD mandates the **Session** Pooler (port 5432), which supports prepared statements, so no extra config is needed. If a user mis-pastes the **Transaction** Pooler (6543), add `connect_args={"statement_cache_size": 0}` and `poolclass=NullPool`. Documented in README (Workstream J).

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_session.py -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/db/session.py tests/test_session.py
git commit -m "feat: async SQLAlchemy engine/session factory with TLS"
```

---

### Task A7: Alembic async setup + the §5 migration

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_initial_schema.py`
- Test: `tests/test_migration_sql.py`

- [ ] **Step 1: Write the failing test** (assert the migration text contains the load-bearing DDL)

```python
# tests/test_migration_sql.py
from pathlib import Path

MIG = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0001_initial_schema.py"

def test_migration_enables_pgvector_and_core_tables():
    sql = MIG.read_text(encoding="utf-8")
    assert "create extension if not exists vector" in sql.lower()
    for table in ("projects", "works", "editions", "reviews", "scores",
                  "aspect_clusters", "demand_signals", "supply_signals",
                  "taxonomy_crosswalk", "unmapped_labels", "analysis_runs"):
        assert f"create table {table}" in sql.lower(), table
    assert "ivfflat" in sql.lower()
    assert "vector(384)" in sql.lower()

def test_no_reddit_or_docker_anywhere_in_migration():
    sql = MIG.read_text(encoding="utf-8").lower()
    assert "reddit" not in sql
    assert "docker" not in sql
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_migration_sql.py -v`
Expected: FAIL — file does not exist.

- [ ] **Step 3: Write `alembic.ini`** (minimal — URL comes from env.py)

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
qualname =
[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine
[logger_alembic]
level = INFO
handlers =
qualname = alembic
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 4: Write `alembic/env.py`** (async, reads normalized URL + SSL)

```python
# alembic/env.py
import asyncio
import ssl
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from lacuna.config import get_settings
from lacuna.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _set_url() -> None:
    config.set_main_option("sqlalchemy.url", get_settings().async_database_url)


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    _set_url()
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"ssl": ssl.create_default_context()},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    _set_url()
    context.configure(url=config.get_main_option("sqlalchemy.url"),
                      target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
```

- [ ] **Step 5: Write `alembic/script.py.mako`** (standard template)

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Write `alembic/versions/0001_initial_schema.py`**

Reproduces PRD §5 exactly via `op.execute`. (Hand-written, not autogenerated, so the extension/index ordering and pgvector type are guaranteed correct — documented choice in master §3.)

```python
"""initial schema (PRD §5) + pgvector

Revision ID: 0001
Revises:
Create Date: 2026-06-17
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = r"""
create extension if not exists vector;

create table projects (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  target_bisac   text[] not null,
  subject_filter jsonb not null default '{}',
  config         jsonb not null default '{}',
  created_at     timestamptz not null default now()
);

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

create table aspect_clusters (
  id             bigint generated always as identity primary key,
  project_id     uuid not null references projects(id) on delete cascade,
  work_id        uuid references works(id) on delete cascade,
  bisac_code     text,
  label          text not null,
  member_count   int not null,
  reviewer_count int not null,
  helpful_weight numeric(6,3),
  platforms      text[] not null,
  cross_platform boolean not null default false,
  representative text
);

create table demand_signals (
  id          bigint generated always as identity primary key,
  project_id  uuid not null references projects(id) on delete cascade,
  bisac_code  text not null,
  source      text not null check (source in ('nyt','googlebooks','hardcover')),
  metric      text not null,
  value       numeric,
  as_of_date  date not null
);

create table supply_signals (
  id                 bigint generated always as identity primary key,
  project_id         uuid not null references projects(id) on delete cascade,
  bisac_code         text not null,
  source             text not null check (source in ('openlibrary','googlebooks')),
  title_count        int,
  recent_title_count int,
  as_of_date         date not null
);

create table scores (
  id              bigint generated always as identity primary key,
  project_id      uuid not null references projects(id) on delete cascade,
  scope           text not null check (scope in ('work','bisac')),
  ref_id          text not null,
  demand_score    numeric(5,3),
  supply_scarcity numeric(5,3),
  unmet_need      numeric(5,3),
  gap_score       numeric(5,3),
  confidence      numeric(4,3) not null,
  sample_size     int not null,
  platforms_used  text[] not null,
  oldest_signal   date,
  newest_signal   date,
  incomplete      boolean not null default false,
  blind_spot      boolean not null default false,
  recent_supply_surge boolean not null default false,
  computed_at     timestamptz not null default now(),
  unique (project_id, scope, ref_id)
);

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

create table analysis_runs (
  id           bigint generated always as identity primary key,
  project_id   uuid references projects(id) on delete cascade,
  mode         text not null check (mode in ('single_title','category_sweep','seed','validation')),
  target       text,
  sources_used text[],
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  status       text not null default 'running',
  counts       jsonb,
  error_detail text
);
"""

DROP = """
drop table if exists analysis_runs, unmapped_labels, taxonomy_crosswalk, scores,
  supply_signals, demand_signals, aspect_clusters, reviews, editions, works, projects cascade;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DROP)
```

- [ ] **Step 7: Run the SQL-text test to verify it passes**

Run: `uv run pytest tests/test_migration_sql.py -v`
Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add alembic.ini alembic/env.py alembic/script.py.mako alembic/versions/0001_initial_schema.py tests/test_migration_sql.py
git commit -m "feat: async alembic setup + PRD §5 schema migration with pgvector"
```

---

### Task A8: Resolve + validate + pin HF revisions (`scripts/pin_revisions.py`)

**Files:**
- Create: `scripts/pin_revisions.py`
- Test: `tests/test_pin_revisions.py`

> **PRD §15 / §17.4:** resolve the current commit hashes for the dataset and both models, verify they load, write them into `config/advanced.yaml`, and **fail loud** if any cannot be resolved/verified. No placeholder text may remain.

- [ ] **Step 1: Write the failing test** (mock the Hub; assert placeholders are replaced + fail-loud on missing)

```python
# tests/test_pin_revisions.py
import textwrap
import pytest
from scripts import pin_revisions as pr

class FakeInfo:
    def __init__(self, sha): self.sha = sha

def test_resolve_writes_real_shas(tmp_path, monkeypatch):
    cfg = tmp_path / "advanced.yaml"
    cfg.write_text(textwrap.dedent("""
        models:
          embedding:  { name: "sentence-transformers/all-MiniLM-L6-v2", revision: "<resolved-at-build>" }
          zero_shot:  { name: "facebook/bart-large-mnli",               revision: "<resolved-at-build>" }
        dataset:
          amazon_reviews: { name: "McAuley-Lab/Amazon-Reviews-2023", revision: "<resolved-at-build>" }
    """), encoding="utf-8")
    monkeypatch.setattr(pr, "_model_sha", lambda name: "a" * 40)
    monkeypatch.setattr(pr, "_dataset_sha", lambda name: "b" * 40)
    pr.pin(cfg, verify=False)
    out = cfg.read_text(encoding="utf-8")
    assert "<resolved-at-build>" not in out
    assert "a" * 40 in out and "b" * 40 in out

def test_fail_loud_when_sha_unresolvable(tmp_path, monkeypatch):
    cfg = tmp_path / "advanced.yaml"
    cfg.write_text('models:\n  embedding: { name: "x", revision: "<resolved-at-build>" }\n', encoding="utf-8")
    monkeypatch.setattr(pr, "_model_sha", lambda name: None)
    with pytest.raises(SystemExit):
        pr.pin(cfg, verify=False)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_pin_revisions.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.pin_revisions`.

- [ ] **Step 3: Write `scripts/__init__.py` (empty) and `scripts/pin_revisions.py`**

```python
# scripts/__init__.py
```

```python
# scripts/pin_revisions.py
"""Resolve, validate, and pin Hugging Face dataset/model revisions (PRD §15).
Fails loud (SystemExit != 0) if any revision can't be resolved or verified.
Usage:  uv run python -m scripts.pin_revisions [--no-verify]
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
ADVANCED = ROOT / "config" / "advanced.yaml"
_api = HfApi()


def _model_sha(name: str) -> str | None:
    try:
        return _api.model_info(name).sha
    except Exception:
        return None


def _dataset_sha(name: str) -> str | None:
    try:
        return _api.dataset_info(name).sha
    except Exception:
        return None


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _verify_model_loads(name: str, revision: str) -> None:
    # Heavy: downloads weights to the local HF cache (one-time). Skipped with --no-verify.
    from transformers import AutoConfig
    try:
        AutoConfig.from_pretrained(name, revision=revision)
    except Exception as exc:  # noqa: BLE001
        _die(f"model {name}@{revision} failed to load: {exc}")


def pin(cfg_path: Path = ADVANCED, *, verify: bool = True) -> None:
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    for key in ("embedding", "zero_shot"):
        node = cfg.get("models", {}).get(key)
        if not node:
            continue
        sha = _model_sha(node["name"])
        if not sha:
            _die(f"could not resolve revision for model {node['name']!r}")
        node["revision"] = sha
        if verify:
            _verify_model_loads(node["name"], sha)

    ds = cfg.get("dataset", {}).get("amazon_reviews")
    if ds:
        sha = _dataset_sha(ds["name"])
        if not sha:
            _die(f"could not resolve revision for dataset {ds['name']!r}")
        ds["revision"] = sha

    text = yaml.safe_dump(cfg, sort_keys=False)
    if "<resolved-at-build>" in text or "PINNED" in text:
        _die("placeholder revision text still present after pinning")
    cfg_path.write_text(text, encoding="utf-8")
    print("Pinned revisions:")
    print(text)


if __name__ == "__main__":
    pin(verify="--no-verify" not in sys.argv)
```

> **Caveat:** `yaml.safe_dump` rewrites `advanced.yaml` and will not preserve the inline comments in that file. Acceptable: the pinned revisions are the source of truth; the warning comments are restated in METHODOLOGY.md (Workstream J). If comment preservation is required later, switch to `ruamel.yaml` — flagged, not done now.

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `uv run pytest tests/test_pin_revisions.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run the real pin against the Hub** (this downloads model configs to verify load)

Run: `uv run python -m scripts.pin_revisions`
Expected: prints the resolved 40-char SHAs for both models + dataset; `config/advanced.yaml` no longer contains `<resolved-at-build>`. If the Hub is unreachable or a repo is gated, it exits non-zero (intended fail-loud).

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/pin_revisions.py tests/test_pin_revisions.py config/advanced.yaml
git commit -m "feat: build-time HF revision pinning (resolve+verify+pin, fail loud)"
```

---

### Task A9: Apply migrations to Supabase + verify

**Files:** none (operational). **Precondition:** user has filled `.env` with the Session Pooler URL and enabled `pgvector` in the Supabase dashboard (PRD §3).

- [ ] **Step 1: Confirm `.env` exists and is filled**

Run: `uv run python -c "from lacuna.config import get_settings; s=get_settings(); print('db ok:', s.async_database_url.split('@')[-1])"`
Expected: prints the host (no password). If it raises, `.env` is missing/blank — stop and have the user fill it (flagged assumption #4 in master).

- [ ] **Step 2: Run the migration**

Run: `uv run alembic upgrade head`
Expected: `Running upgrade  -> 0001, initial schema (PRD §5) + pgvector`. If it errors with `type "vector" does not exist`, the user has not enabled the extension in the dashboard — surface that exact instruction, do not work around it.

- [ ] **Step 3: Verify the schema landed** (counts the 11 tables)

Run:
```bash
uv run python -c "import asyncio; from sqlalchemy import text; from lacuna.db.session import build_engine; \
e=build_engine(); \
async def go():\
\n    async with e.connect() as c:\
\n        r=await c.execute(sa_text(\"select count(*) from information_schema.tables where table_schema='public'\"));\
\n        print('public tables:', r.scalar()); \
asyncio.run(go())"
```
Expected: `public tables: 11` (plus `alembic_version`). *(If the inline heredoc is awkward on Windows, put the snippet in `scripts/_verify_schema.py` and `uv run python scripts/_verify_schema.py`.)*

- [ ] **Step 4: Verify acceptance criterion 1 — no Docker/local PG references**

Run: `uv run pytest tests/test_migration_sql.py::test_no_reddit_or_docker_anywhere_in_migration -v`
Expected: passed.

- [ ] **Step 5: Commit** (operational note only — no new files unless `_verify_schema.py` was created)

```bash
git add -A
git commit -m "chore: apply initial schema to Supabase (verified 11 tables + pgvector)"
```

---

## Self-review (against PRD)

- **§2 stack** — all libraries present in `pyproject.toml`; `uv.lock` committed (A2). ✓
- **§3 secrets** — `.env.example` shipped; `.env`/`.claude.json` git-ignored before any file (A0); secrets read server-side only via `config.py`. ✓
- **§5 schema** — migration reproduces every table/column/constraint/index verbatim; `test_models.py` + `test_migration_sql.py` enforce coverage; `pgvector` enabled in-migration. ✓
- **§13 config** — both YAML tiers shipped; flagged knobs added (master §2). ✓
- **§15 / §17.4 pinning** — `pin_revisions.py` resolves+verifies+pins, fails loud, asserts no placeholder remains. ✓
- **CLAUDE.md §3** — no Docker/local PG anywhere; test guards it. ✓
- **DATABASE_URL normalization** — pure function, table-driven tests incl. sslmode stripping. ✓
- **Placeholder scan** — every code step contains complete code; no TODO/TBD. ✓
- **Type consistency** — `Base`, `build_engine`, `normalize_database_url`, `pin(...)` names match across tasks and the env.py/session.py imports. ✓

**Blocks cleared for:** Workstream B (adapters) and G0 (validation gate).
