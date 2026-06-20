# Lacuna Frontend — Backend (W1→W4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a FastAPI backend that wraps the existing `lacuna` engine as a REST API — projects/reads/export, a `jobs` status system, batch-seed-as-subprocess, and the **new live single-title glue** — ending at the W4 gate where live search is proven against a real title.

**Architecture:** A new top-level `api/` package imports the `lacuna` engine and exposes it over HTTP. NLP models load **once** at startup (FastAPI lifespan) into a singleton held on `app.state`; heavy CPU (embed/cluster) runs off the event loop via `run_in_threadpool`. The batch seed stays a CPU-heavy subprocess of the existing CLI and reports progress into a new `jobs` table; live search is new glue (`lacuna/pipeline/live_single_title.py`) composing existing Hardcover + NLP + merge + score + export. No engine internals are rewritten.

**Tech Stack:** FastAPI, Uvicorn, Starlette `run_in_threadpool`, SQLAlchemy 2.0 async + asyncpg, Alembic, the existing `lacuna` package, pytest + pytest-asyncio (`asyncio_mode=auto`), httpx `ASGITransport` for in-process API tests.

## Global Constraints

Copied verbatim from `Lacuna_Frontend_PRD.md` and `CLAUDE.md`; every task implicitly includes these.

- **Engine is reused via import, never rewritten** (Frontend PRD §13.1). The only new engine code is `lacuna/pipeline/live_single_title.py` (§3.2).
- **Two execution models never merge** (Frontend PRD §1.2 / §13.2): corpus = batch (subprocess, ~1h); Hardcover = live (seconds). The corpus is **never** queried on a user search.
- **Models load once at backend startup, stay warm** (§13.4); live search never reloads them. The batch seed subprocess loads its own.
- **Heavy CPU off the event loop** (§13.5) via a worker/thread pool; the seed is a subprocess.
- **One job system** — the `jobs` table (§13.6) is the only schema addition (§13.12); `analysis_runs` stays for engine observability. Reuse all existing tables + `project_id` isolation; add no per-row auth (§9).
- **Frontend holds no secrets** (§13.7 / §15): no API key or secret value is ever returned in a response body.
- **Local NLP boundary** (`CLAUDE.md` §3): zero raw review text reaches any external LLM API; the app runs end-to-end at $0 with keys unset.
- **Database:** Supabase only via the Session Pooler string in `.env`; Docker/local Postgres banned (`CLAUDE.md` §3).
- **Run tooling via the venv** (memory): `.venv\Scripts\python.exe`, `.venv\Scripts\pytest.exe`, `.venv\Scripts\alembic.exe`, `.venv\Scripts\uvicorn.exe`, `.venv\Scripts\lacuna.exe`. `uv` is NOT on PATH in non-interactive shells.
- **pytest is `asyncio_mode=auto`** (pyproject): `async def test_*` needs no decorator. New DB-touching tests must be skippable when `DATABASE_URL`/live creds are absent, mirroring `tests/test_hardcover_live.py`.
- **Pin discipline / fail loud** (`CLAUDE.md` §3): never ship placeholder revision hashes; the warm loader surfaces the engine's existing "revision not pinned" error rather than masking it.

---

## File Structure

New `api/` package (HTTP layer only — no business logic beyond delegation):

- `api/__init__.py` — package marker.
- `api/runtime.py` — `EngineRuntime` singleton: warm `Embedder` + `AspectLabeler`, exposed via `app.state.runtime`. One place that owns model lifetime.
- `api/app.py` — `create_app()` factory: lifespan (warm models), `CORSMiddleware`, router registration, `/health`.
- `api/schemas.py` — Pydantic request/response DTOs (API contract; never leaks ORM rows or secrets).
- `api/deps.py` — shared dependencies: `get_sessionmaker()`, `get_runtime(request)`.
- `api/jobs.py` — jobs service: `create_job`, `get_job`, `update_job`, `list_jobs` over the `jobs` table.
- `api/routers/projects.py` — projects CRUD.
- `api/routers/reads.py` — works / clusters / scores / candidates read endpoints.
- `api/routers/export.py` — Context Pack export endpoint.
- `api/routers/seed.py` — start batch seed subprocess → job.
- `api/routers/search.py` — live single-title search → job (W4).
- `api/routers/jobs.py` — job status + project job list.

Engine additions (thin):

- `lacuna/db/models.py` — **modify**: add `Job` ORM model mirroring the migration.
- `alembic/versions/0003_jobs_table.py` — **create**: the `jobs` table (Frontend PRD §5).
- `lacuna/seed/seed.py` — **modify**: accept an optional `progress_cb` so the seed can report into `jobs` (does not change seed math).
- `lacuna/pipeline/live_single_title.py` — **create**: the new live glue (§3.2).

Tests:

- `tests/api/__init__.py`, `tests/api/conftest.py` — in-process app fixture (httpx ASGITransport) + a fake runtime.
- `tests/api/test_health.py`, `tests/api/test_projects.py`, `tests/api/test_reads.py`, `tests/api/test_export.py`, `tests/api/test_seed_endpoint.py`, `tests/api/test_search_endpoint.py`, `tests/api/test_jobs.py`.
- `tests/test_migration_sql.py` — **modify**: assert the `jobs` DDL parses (matches existing migration-SQL test pattern).
- `tests/pipeline/test_live_single_title.py` — offline glue test with fakes (no network/models).
- `tests/test_live_search_gate.py` — **W4 GATE**: live, skipped unless `HARDCOVER_API_TOKEN` set.

---

## W1 — Backend Skeleton

### Task 1: `jobs` table — migration + ORM model

**Files:**
- Create: `alembic/versions/0003_jobs_table.py`
- Modify: `lacuna/db/models.py` (append `Job` model)
- Modify: `tests/test_migration_sql.py`

**Interfaces:**
- Produces: `Job` ORM model with columns `id, project_id, kind, status, progress_pct, step, counts, result_ref, error_detail, created_at, updated_at`; alembic revision `0003` (down_revision `0002`).

- [ ] **Step 1: Write the failing model test**

In `tests/test_models.py` (append a new test):

```python
def test_job_model_columns():
    from lacuna.db.models import Job
    cols = Job.__table__.columns
    assert {"id", "project_id", "kind", "status", "progress_pct", "step",
            "counts", "result_ref", "error_detail", "created_at", "updated_at"} <= set(cols.keys())
    assert Job.__tablename__ == "jobs"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/test_models.py::test_job_model_columns -q`
Expected: FAIL with `ImportError: cannot import name 'Job'`.

- [ ] **Step 3: Add the `Job` model**

Append to `lacuna/db/models.py`:

```python
class Job(Base):
    """UI-facing async-work status surface (Frontend PRD §5). One row per
    seed/live_search/sweep run; the UI polls it. `analysis_runs` stays for
    engine-level observability — `jobs` is the product status table."""
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("kind in ('seed','live_search','sweep')"),
        CheckConstraint("status in ('queued','running','done','error')"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=sa_text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sa_text("'queued'"))
    progress_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default=sa_text("0"))
    step: Mapped[str | None] = mapped_column(Text)
    counts: Mapped[dict | None] = mapped_column(JSONB)
    result_ref: Mapped[str | None] = mapped_column(Text)
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))
```

- [ ] **Step 4: Run the model test to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/test_models.py::test_job_model_columns -q`
Expected: PASS.

- [ ] **Step 5: Write the migration**

Create `alembic/versions/0003_jobs_table.py`:

```python
"""jobs table — UI-facing async status surface (Frontend PRD §5)

Adds the single new table the frontend PRD permits. No other schema change.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-19
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_DDL = """
create table if not exists jobs (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid references projects(id) on delete cascade,
  kind         text not null check (kind in ('seed','live_search','sweep')),
  status       text not null default 'queued' check (status in ('queued','running','done','error')),
  progress_pct numeric(5,2) not null default 0,
  step         text,
  counts       jsonb,
  result_ref   text,
  error_detail text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists jobs_project_idx on jobs (project_id, created_at desc);
"""


def upgrade() -> None:
    op.execute(_DDL)


def downgrade() -> None:
    op.execute("drop table if exists jobs")
```

- [ ] **Step 6: Add a migration-SQL parse test**

Append to `tests/test_migration_sql.py` (follow the file's existing import/style — it loads a migration module and asserts on its SQL string):

```python
def test_jobs_migration_creates_table_and_index():
    import importlib
    mod = importlib.import_module("alembic.versions.0003_jobs_table")
    sql = mod._DDL.lower()
    assert "create table" in sql and "jobs" in sql
    assert "check (kind in ('seed','live_search','sweep'))" in sql
    assert "jobs_project_idx" in sql
    assert mod.revision == "0003" and mod.down_revision == "0002"
```

> If `tests/test_migration_sql.py` imports migrations differently (e.g. by file path), match that existing mechanism instead of `import_module`.

- [ ] **Step 7: Run the migration tests**

Run: `.venv\Scripts\pytest.exe tests/test_migration_sql.py -q`
Expected: PASS.

- [ ] **Step 8: Apply the migration to Supabase**

Run: `.venv\Scripts\alembic.exe upgrade head`
Expected: `Running upgrade 0002 -> 0003, jobs table`. **Per `CLAUDE.md` §2, verify it applied before any code writes to `jobs`** — confirm with:
Run: `.venv\Scripts\alembic.exe current`
Expected: shows `0003 (head)`.

- [ ] **Step 9: Commit**

```bash
git add lacuna/db/models.py alembic/versions/0003_jobs_table.py tests/test_models.py tests/test_migration_sql.py
git commit -m "feat(api): add jobs table (migration 0003) + Job ORM model"
```

---

### Task 2: Engine runtime singleton (warm models)

**Files:**
- Create: `api/__init__.py` (empty), `api/runtime.py`
- Test: `tests/api/__init__.py` (empty), `tests/api/test_runtime.py`

**Interfaces:**
- Produces: `class EngineRuntime` with `embedder: Embedder`, `labeler: AspectLabeler`, classmethod `warm() -> EngineRuntime` (constructs both and forces model load), and `for_testing(embedder, labeler) -> EngineRuntime` (inject fakes, no load).

- [ ] **Step 1: Write the failing test**

`tests/api/test_runtime.py`:

```python
from api.runtime import EngineRuntime


class _FakeEmbedder:
    def encode(self, texts):
        return [[0.0] for _ in texts]


class _FakeLabeler:
    def label_cluster(self, texts, candidate_labels=None):
        return None


def test_runtime_holds_injected_components_without_loading_models():
    rt = EngineRuntime.for_testing(embedder=_FakeEmbedder(), labeler=_FakeLabeler())
    assert rt.embedder is not None
    assert rt.labeler is not None
    # injected components must be used verbatim (no model download in tests)
    assert rt.embedder.encode(["x"]) == [[0.0]]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_runtime.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'api'`.

- [ ] **Step 3: Implement the runtime**

`api/__init__.py`: empty file.
`tests/api/__init__.py`: empty file.
`api/runtime.py`:

```python
# api/runtime.py
"""Warm-model singleton (Frontend PRD §2/§13.4). The ~1.6GB zero-shot model and the
embedding model load ONCE here at backend startup and stay in memory; live search
reuses them and never reloads. Tests inject fakes via `for_testing` so no model is
downloaded. Nothing here sends text off the machine (CLAUDE.md §3)."""
from __future__ import annotations

from dataclasses import dataclass

from lacuna.nlp.aspects import AspectLabeler
from lacuna.nlp.embeddings import Embedder


@dataclass
class EngineRuntime:
    embedder: Embedder
    labeler: AspectLabeler

    @classmethod
    def warm(cls) -> "EngineRuntime":
        """Construct and force model load. Surfaces the engine's 'revision not
        pinned' error loudly (CLAUDE.md §3) rather than masking it."""
        embedder = Embedder()
        labeler = AspectLabeler()
        _ = embedder.encoder      # triggers SentenceTransformer load (pinned revision)
        _ = labeler.classifier    # triggers bart-large-mnli load (pinned revision)
        return cls(embedder=embedder, labeler=labeler)

    @classmethod
    def for_testing(cls, *, embedder, labeler) -> "EngineRuntime":
        return cls(embedder=embedder, labeler=labeler)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/api/test_runtime.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/__init__.py api/runtime.py tests/api/__init__.py tests/api/test_runtime.py
git commit -m "feat(api): EngineRuntime warm-model singleton (PRD §13.4)"
```

---

### Task 3: App factory, lifespan, CORS, `/health`

**Files:**
- Create: `api/app.py`, `api/deps.py`
- Create: `tests/api/conftest.py`, `tests/api/test_health.py`
- Modify: `pyproject.toml` (add `fastapi`, `uvicorn[standard]`)

**Interfaces:**
- Consumes: `EngineRuntime` (Task 2).
- Produces: `create_app(runtime=None, sessionmaker=None) -> FastAPI`; `app.state.runtime`, `app.state.sessionmaker`; `GET /health` → `{"status": "...", "models_ready": bool}`. `api/deps.py`: `get_runtime(request) -> EngineRuntime`, `get_sessionmaker(request) -> async_sessionmaker`.

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, add to `[project].dependencies`:

```toml
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
```

Run: `.venv\Scripts\python.exe -m pip install "fastapi>=0.111" "uvicorn[standard]>=0.30"`
Expected: installs successfully.

- [ ] **Step 2: Write the failing health test + fixture**

`tests/api/conftest.py`:

```python
import httpx
import pytest

from api.app import create_app
from api.runtime import EngineRuntime


class FakeEmbedder:
    def encode(self, texts):
        import numpy as np
        return np.array([[float(len(t)), 1.0, 0.0, 0.0] for t in texts])


class FakeLabeler:
    def label_cluster(self, texts, candidate_labels=None):
        from lacuna.nlp.aspects import AspectResult
        return AspectResult(label="outdated", score=0.9,
                            representative="Readers say the material feels outdated.")


@pytest.fixture
def runtime():
    return EngineRuntime.for_testing(embedder=FakeEmbedder(), labeler=FakeLabeler())


@pytest.fixture
async def client(runtime):
    app = create_app(runtime=runtime, sessionmaker=None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

`tests/api/test_health.py`:

```python
async def test_health_reports_models_ready(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["models_ready"] is True
    assert body["status"] == "ok"
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_health.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.app'`.

- [ ] **Step 4: Implement the app factory + deps**

`api/deps.py`:

```python
# api/deps.py
from __future__ import annotations

from fastapi import Request

from api.runtime import EngineRuntime


def get_runtime(request: Request) -> EngineRuntime:
    return request.app.state.runtime


def get_sessionmaker(request: Request):
    sm = request.app.state.sessionmaker
    if sm is None:
        from lacuna.db.session import build_sessionmaker
        sm = build_sessionmaker()
        request.app.state.sessionmaker = sm
    return sm
```

`api/app.py`:

```python
# api/app.py
"""FastAPI app factory (Frontend PRD §2/§4). Wraps the lacuna engine. Models warm
once in the lifespan; CORS is restricted to the local frontend; secrets never leave
the backend. The factory takes injectable runtime/sessionmaker so tests run with
fakes and no model download."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.runtime import EngineRuntime

ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(*, runtime: EngineRuntime | None = None, sessionmaker=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Warm models once at startup unless one was injected (tests/dev).
        if app.state.runtime is None:
            app.state.runtime = EngineRuntime.warm()
        yield

    app = FastAPI(title="Lacuna API", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.sessionmaker = sessionmaker

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        ready = app.state.runtime is not None
        return {"status": "ok" if ready else "warming", "models_ready": ready}

    # Routers are registered in later tasks:
    # from api.routers import projects, reads, export, seed, search, jobs
    # for r in (projects, reads, export, seed, search, jobs):
    #     app.include_router(r.router)

    return app
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/api/test_health.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app.py api/deps.py tests/api/conftest.py tests/api/test_health.py pyproject.toml
git commit -m "feat(api): FastAPI app factory with warm-model lifespan, CORS, /health"
```

---

### Task 4: Jobs service (create / get / update / list)

**Files:**
- Create: `api/jobs.py`
- Test: `tests/api/test_jobs_service.py`

**Interfaces:**
- Consumes: `Job` model (Task 1), an `async_sessionmaker`.
- Produces (all async, all take `sm: async_sessionmaker` as first arg):
  - `create_job(sm, *, kind: str, project_id: uuid.UUID | None) -> uuid.UUID`
  - `get_job(sm, job_id: uuid.UUID) -> dict | None` → `{id, project_id, kind, status, progress_pct, step, counts, result_ref, error_detail}`
  - `update_job(sm, job_id, *, status=None, progress_pct=None, step=None, counts=None, result_ref=None, error_detail=None) -> None`
  - `list_jobs(sm, project_id: uuid.UUID, *, limit: int = 20) -> list[dict]`

- [ ] **Step 1: Write the failing test (DB-gated)**

`tests/api/test_jobs_service.py`:

```python
import os
import uuid

import pytest

from lacuna.db.session import build_sessionmaker
from api import jobs as jobs_svc

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — jobs service DB test skipped",
)


async def test_job_lifecycle_create_update_get():
    sm = build_sessionmaker()
    jid = await jobs_svc.create_job(sm, kind="live_search", project_id=None)
    assert isinstance(jid, uuid.UUID)

    row = await jobs_svc.get_job(sm, jid)
    assert row["status"] == "queued"
    assert row["kind"] == "live_search"

    await jobs_svc.update_job(sm, jid, status="running", progress_pct=50, step="clustering")
    row = await jobs_svc.get_job(sm, jid)
    assert row["status"] == "running"
    assert float(row["progress_pct"]) == 50.0
    assert row["step"] == "clustering"

    await jobs_svc.update_job(sm, jid, status="done", progress_pct=100, result_ref="pack.json")
    row = await jobs_svc.get_job(sm, jid)
    assert row["status"] == "done"
    assert row["result_ref"] == "pack.json"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_jobs_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.jobs'` (or skip if no DB; set `DATABASE_URL` from `.env` to actually run it).

- [ ] **Step 3: Implement the jobs service**

`api/jobs.py`:

```python
# api/jobs.py
"""Jobs service (Frontend PRD §13.6): the one async-status surface the UI polls.
Thin CRUD over the `jobs` table; engine math lives elsewhere."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from lacuna.db.models import Job


def _row_to_dict(j: Job) -> dict:
    return {
        "id": str(j.id), "project_id": str(j.project_id) if j.project_id else None,
        "kind": j.kind, "status": j.status, "progress_pct": float(j.progress_pct),
        "step": j.step, "counts": j.counts, "result_ref": j.result_ref,
        "error_detail": j.error_detail,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


async def create_job(sm: async_sessionmaker, *, kind: str,
                     project_id: uuid.UUID | None) -> uuid.UUID:
    async with sm() as session:
        async with session.begin():
            job = Job(kind=kind, project_id=project_id, status="queued")
            session.add(job)
            await session.flush()
            return job.id


async def get_job(sm: async_sessionmaker, job_id: uuid.UUID) -> dict | None:
    async with sm() as session:
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
        return _row_to_dict(job) if job else None


async def update_job(sm: async_sessionmaker, job_id: uuid.UUID, *, status=None,
                     progress_pct=None, step=None, counts=None,
                     result_ref=None, error_detail=None) -> None:
    async with sm() as session:
        async with session.begin():
            job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
            if job is None:
                return
            if status is not None: job.status = status
            if progress_pct is not None: job.progress_pct = progress_pct
            if step is not None: job.step = step
            if counts is not None: job.counts = counts
            if result_ref is not None: job.result_ref = result_ref
            if error_detail is not None: job.error_detail = error_detail
            job.updated_at = dt.datetime.now(dt.timezone.utc)


async def list_jobs(sm: async_sessionmaker, project_id: uuid.UUID, *, limit: int = 20) -> list[dict]:
    async with sm() as session:
        rows = (await session.execute(
            select(Job).where(Job.project_id == project_id)
            .order_by(Job.created_at.desc()).limit(limit))).scalars().all()
        return [_row_to_dict(r) for r in rows]
```

- [ ] **Step 4: Run to verify it passes (with DATABASE_URL set)**

Run: `.venv\Scripts\pytest.exe tests/api/test_jobs_service.py -q`
Expected: PASS (or SKIP if `DATABASE_URL` unset — set it from `.env` to exercise against Supabase per `CLAUDE.md` §2 before relying on it).

- [ ] **Step 5: Commit**

```bash
git add api/jobs.py tests/api/test_jobs_service.py
git commit -m "feat(api): jobs service CRUD over jobs table"
```

---

## W2 — Engine Wrap (Read Paths)

### Task 5: Projects CRUD endpoints

**Files:**
- Create: `api/schemas.py`, `api/routers/__init__.py` (empty), `api/routers/projects.py`
- Modify: `api/app.py` (register the router)
- Test: `tests/api/test_projects.py`

**Interfaces:**
- Consumes: `get_sessionmaker`, `Project`/`Work`/`AspectCluster` models, `lacuna.db.repository._get_or_create_project`.
- Produces: `GET /projects`, `POST /projects`, `GET /projects/{id}`, `DELETE /projects/{id}`. Response DTO `ProjectOut {id, name, target_bisac, subject_filter, seeded, work_count, cluster_count, created_at}`.

- [ ] **Step 1: Write the failing test (DB-gated)**

`tests/api/test_projects.py`:

```python
import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_create_list_get_delete_project(client):
    body = {"name": "Test Niche — API", "target_bisac": ["COM051000"],
            "subject_filter": {"keywords": ["python"]}, "config": {}}
    created = (await client.post("/projects", json=body)).json()
    pid = created["id"]
    assert created["name"] == body["name"]
    assert created["seeded"] is False
    assert created["work_count"] == 0

    listed = (await client.get("/projects")).json()
    assert any(p["id"] == pid for p in listed)

    got = (await client.get(f"/projects/{pid}")).json()
    assert got["id"] == pid

    # PUT — persist an intent knob into config (Settings surface)
    updated = (await client.put(f"/projects/{pid}",
                                json={"config": {"timely_evergreen": 0.7}})).json()
    assert updated["id"] == pid
    refetched = (await client.get(f"/projects/{pid}")).json()
    assert refetched["id"] == pid  # config round-trips (not surfaced in ProjectOut, but persisted)

    assert (await client.delete(f"/projects/{pid}")).status_code == 204
    assert (await client.get(f"/projects/{pid}")).status_code == 404
```

> The `client` fixture (Task 3) injects `sessionmaker=None`; for DB-gated tests, extend `conftest.py` so when `DATABASE_URL` is set the app uses the real sessionmaker. Add to `conftest.py`:
> ```python
> @pytest.fixture
> async def client(runtime):
>     import os
>     sm = None
>     if os.getenv("DATABASE_URL"):
>         from lacuna.db.session import build_sessionmaker
>         sm = build_sessionmaker()
>     app = create_app(runtime=runtime, sessionmaker=sm)
>     transport = httpx.ASGITransport(app=app)
>     async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
>         yield c
> ```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_projects.py -q`
Expected: FAIL — 404 on `POST /projects` (route not registered).

- [ ] **Step 3: Add the schemas**

`api/schemas.py`:

```python
# api/schemas.py
"""API DTOs. The HTTP contract — deliberately decoupled from ORM rows, and never
carries a secret value (Frontend PRD §13.7)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    target_bisac: list[str] = Field(default_factory=list)
    subject_filter: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    """Partial update — Settings persists intent knobs into `config` (Frontend PRD
    §10). All fields optional; only provided fields are written."""
    name: str | None = None
    target_bisac: list[str] | None = None
    subject_filter: dict | None = None
    config: dict | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    target_bisac: list[str]
    subject_filter: dict
    seeded: bool
    work_count: int
    cluster_count: int
    created_at: str | None = None


class SearchRequest(BaseModel):
    title: str | None = None
    isbn: str | None = None


class SeedRequest(BaseModel):
    meta_limit: int = 200_000
    review_limit: int = 1_000_000
    max_works: int = 25


class JobOut(BaseModel):
    id: str
    project_id: str | None
    kind: str
    status: str
    progress_pct: float
    step: str | None = None
    counts: dict | None = None
    result_ref: str | None = None
    error_detail: str | None = None
```

- [ ] **Step 4: Implement the projects router**

`api/routers/__init__.py`: empty.
`api/routers/projects.py`:

```python
# api/routers/projects.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select

from api.deps import get_sessionmaker
from api.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from lacuna.db.models import AspectCluster, Project, Work

router = APIRouter(prefix="/projects", tags=["projects"])


async def _project_out(session, p: Project) -> ProjectOut:
    wc = (await session.execute(
        select(func.count()).select_from(Work).where(Work.project_id == p.id))).scalar_one()
    cc = (await session.execute(
        select(func.count()).select_from(AspectCluster).where(AspectCluster.project_id == p.id))).scalar_one()
    return ProjectOut(
        id=str(p.id), name=p.name, target_bisac=list(p.target_bisac or []),
        subject_filter=p.subject_filter or {}, seeded=wc > 0,
        work_count=wc, cluster_count=cc,
        created_at=p.created_at.isoformat() if p.created_at else None)


@router.get("", response_model=list[ProjectOut])
async def list_projects(sm=Depends(get_sessionmaker)):
    async with sm() as session:
        projs = (await session.execute(select(Project).order_by(Project.created_at.desc()))).scalars().all()
        return [await _project_out(session, p) for p in projs]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectCreate, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        async with session.begin():
            p = Project(name=body.name, target_bisac=body.target_bisac,
                        subject_filter=body.subject_filter, config=body.config)
            session.add(p)
            await session.flush()
            return await _project_out(session, p)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        p = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        return await _project_out(session, p)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: uuid.UUID, body: ProjectUpdate, sm=Depends(get_sessionmaker)):
    """Partial update; powers Settings (intent knobs into config, Frontend PRD §10).
    Correctness knobs are never accepted here — the UI only sends intent knobs."""
    async with sm() as session:
        async with session.begin():
            p = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
            if p is None:
                raise HTTPException(status_code=404, detail="project not found")
            if body.name is not None: p.name = body.name
            if body.target_bisac is not None: p.target_bisac = body.target_bisac
            if body.subject_filter is not None: p.subject_filter = body.subject_filter
            if body.config is not None: p.config = body.config
            await session.flush()
            return await _project_out(session, p)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        async with session.begin():
            res = await session.execute(delete(Project).where(Project.id == project_id))
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="project not found")
```

- [ ] **Step 5: Register the router in `api/app.py`**

Replace the commented router block in `create_app` with:

```python
    from api.routers import projects
    app.include_router(projects.router)
```

- [ ] **Step 6: Run to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/api/test_projects.py -q`
Expected: PASS (with `DATABASE_URL` set) — creates, lists, gets, deletes a throwaway project.

- [ ] **Step 7: Commit**

```bash
git add api/schemas.py api/routers/__init__.py api/routers/projects.py api/app.py tests/api/conftest.py tests/api/test_projects.py
git commit -m "feat(api): projects CRUD endpoints"
```

---

### Task 6: Read endpoints — works / clusters / scores / candidates

**Files:**
- Create: `api/routers/reads.py`
- Modify: `api/app.py` (register)
- Test: `tests/api/test_reads.py`

**Interfaces:**
- Produces:
  - `GET /projects/{id}/works` → list of `{id, title, author, agg_rating_avg, agg_rating_count, review_count}`
  - `GET /projects/{id}/works/{workId}` → work detail + its clusters
  - `GET /projects/{id}/clusters?scope=work|bisac&ref=...` → cluster rows
  - `GET /projects/{id}/scores` → score rows
  - `GET /projects/{id}/candidates` → ranked scores joined to titles (gap_score desc) — powers the sweep UI

- [ ] **Step 1: Write the failing test (DB-gated, read-only against the seeded project)**

`tests/api/test_reads.py`:

```python
import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def _seeded_project_id(client):
    projs = (await client.get("/projects")).json()
    seeded = [p for p in projs if p["seeded"]]
    return seeded[0]["id"] if seeded else None


async def test_works_and_clusters_read(client):
    pid = await _seeded_project_id(client)
    if pid is None:
        pytest.skip("no seeded project in this DB")
    works = (await client.get(f"/projects/{pid}/works")).json()
    assert isinstance(works, list)
    if works:
        wid = works[0]["id"]
        detail = (await client.get(f"/projects/{pid}/works/{wid}")).json()
        assert detail["id"] == wid
        assert "clusters" in detail


async def test_candidates_ranked_desc(client):
    pid = await _seeded_project_id(client)
    if pid is None:
        pytest.skip("no seeded project in this DB")
    cands = (await client.get(f"/projects/{pid}/candidates")).json()
    gaps = [c["gap_score"] for c in cands]
    assert gaps == sorted(gaps, reverse=True)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_reads.py -q`
Expected: FAIL — 404 (routes not registered).

- [ ] **Step 3: Implement the reads router**

`api/routers/reads.py`:

```python
# api/routers/reads.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from api.deps import get_sessionmaker
from lacuna.db.models import AspectCluster, Review, Score, Work

router = APIRouter(prefix="/projects/{project_id}", tags=["reads"])


def _cluster_dict(c: AspectCluster) -> dict:
    return {"id": c.id, "label": c.label, "representative": c.representative,
            "member_count": c.member_count, "reviewer_count": c.reviewer_count,
            "helpful_weight": float(c.helpful_weight or 0.0), "platforms": list(c.platforms or []),
            "cross_platform": bool(c.cross_platform), "work_id": str(c.work_id) if c.work_id else None,
            "bisac_code": c.bisac_code}


@router.get("/works")
async def list_works(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        works = (await session.execute(
            select(Work).where(Work.project_id == project_id))).scalars().all()
        rc = dict((await session.execute(
            select(Review.work_id, func.count()).where(Review.project_id == project_id)
            .group_by(Review.work_id))).all())
        return [{"id": str(w.id), "title": w.title, "author": w.author,
                 "agg_rating_avg": float(w.agg_rating_avg) if w.agg_rating_avg is not None else None,
                 "agg_rating_count": w.agg_rating_count,
                 "review_count": rc.get(w.id, 0)} for w in works]


@router.get("/works/{work_id}")
async def work_detail(project_id: uuid.UUID, work_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        w = (await session.execute(
            select(Work).where(Work.id == work_id, Work.project_id == project_id))).scalar_one_or_none()
        if w is None:
            raise HTTPException(status_code=404, detail="work not found")
        clusters = (await session.execute(
            select(AspectCluster).where(AspectCluster.work_id == work_id))).scalars().all()
        review_count = (await session.execute(
            select(func.count()).select_from(Review).where(Review.work_id == work_id))).scalar_one()
        return {"id": str(w.id), "title": w.title, "author": w.author,
                "agg_rating_avg": float(w.agg_rating_avg) if w.agg_rating_avg is not None else None,
                "agg_rating_count": w.agg_rating_count, "review_count": review_count,
                "clusters": [_cluster_dict(c) for c in clusters]}


@router.get("/clusters")
async def list_clusters(project_id: uuid.UUID, scope: str = Query("work"),
                        ref: str | None = None, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        stmt = select(AspectCluster).where(AspectCluster.project_id == project_id)
        if scope == "bisac":
            stmt = stmt.where(AspectCluster.work_id.is_(None))
            if ref:
                stmt = stmt.where(AspectCluster.bisac_code == ref)
        else:
            stmt = stmt.where(AspectCluster.work_id.is_not(None))
            if ref:
                stmt = stmt.where(AspectCluster.work_id == uuid.UUID(ref))
        rows = (await session.execute(stmt)).scalars().all()
        return [_cluster_dict(c) for c in rows]


def _score_dict(s: Score) -> dict:
    return {"scope": s.scope, "ref_id": s.ref_id,
            "gap_score": float(s.gap_score) if s.gap_score is not None else 0.0,
            "demand_score": float(s.demand_score) if s.demand_score is not None else 0.0,
            "supply_scarcity": float(s.supply_scarcity) if s.supply_scarcity is not None else 0.0,
            "unmet_need": float(s.unmet_need) if s.unmet_need is not None else 0.0,
            "confidence": float(s.confidence), "sample_size": s.sample_size,
            "platforms_used": list(s.platforms_used or []),
            "incomplete": s.incomplete, "blind_spot": s.blind_spot,
            "recent_supply_surge": s.recent_supply_surge}


@router.get("/scores")
async def list_scores(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        rows = (await session.execute(
            select(Score).where(Score.project_id == project_id))).scalars().all()
        return [_score_dict(s) for s in rows]


@router.get("/candidates")
async def list_candidates(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    """Ranked candidates (gap_score desc), each joined to a human title. Work scope
    -> work title; bisac scope -> 'CODE — niche complaint clusters'."""
    async with sm() as session:
        scores = (await session.execute(
            select(Score).where(Score.project_id == project_id)
            .order_by(Score.gap_score.desc().nullslast()))).scalars().all()
        works = {str(w.id): w for w in (await session.execute(
            select(Work).where(Work.project_id == project_id))).scalars().all()}
        out = []
        for s in scores:
            d = _score_dict(s)
            if s.scope == "work":
                w = works.get(s.ref_id)
                d["title"] = w.title if w else s.ref_id
            else:
                code = s.ref_id.split(":", 1)[-1]
                d["title"] = f"{code} — niche complaint clusters"
            out.append(d)
        return out
```

- [ ] **Step 4: Register in `api/app.py`**

```python
    from api.routers import projects, reads
    app.include_router(projects.router)
    app.include_router(reads.router)
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/api/test_reads.py -q`
Expected: PASS (reads the existing seeded "Example - Programming & Software Books" project).

- [ ] **Step 6: Commit**

```bash
git add api/routers/reads.py api/app.py tests/api/test_reads.py
git commit -m "feat(api): read endpoints for works/clusters/scores/candidates"
```

---

### Task 7: Parameterize the distiller by `project_id` + export endpoint

**Files:**
- Modify: `lacuna/pipeline/distill.py` (resolve project by id when given)
- Create: `api/routers/export.py`
- Modify: `api/app.py` (register)
- Test: `tests/export/test_distill_project_id.py`, `tests/api/test_export.py`

**Interfaces:**
- Modifies (engine extension, not rewrite): `distill_score_export(*, out="pack.json", mode="category_sweep", project_id: uuid.UUID | str | None = None) -> dict`. When `project_id` is given, the distiller resolves **that** project by id; when `None`, it falls back to the config-named project (preserves the existing CLI behavior). Also adds a helper `_load_project_by_id(session, project_id)`.
- Produces: `GET /projects/{id}/export?format=json|md&scope=...` → the pack for **that** project, regenerated via the (now id-aware) distiller off the event loop.

> **Why now, not deferred (per your call):** resolving the distiller by `config.project_name` silently exports the *configured* niche regardless of which project the URL names — that breaks the multi-project model (Frontend PRD §9, isolation by `project_id`). This is the one place the export path must become id-aware. It's an additive parameter (the CLI path keeps working with `project_id=None`), so it honors §13.1 reuse while fixing the correctness hole.

- [ ] **Step 1: Write the failing distiller test**

`tests/export/test_distill_project_id.py`:

```python
import inspect

from lacuna.pipeline.distill import distill_score_export


def test_distill_accepts_project_id_param():
    sig = inspect.signature(distill_score_export)
    assert "project_id" in sig.parameters, "distiller must be id-aware for multi-project export"
    assert sig.parameters["project_id"].default is None  # CLI path unchanged when omitted
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/export/test_distill_project_id.py -q`
Expected: FAIL — `AssertionError: distiller must be id-aware`.

- [ ] **Step 3: Make the distiller id-aware**

In `lacuna/pipeline/distill.py`, add the id resolver and thread `project_id` through:

```python
import uuid as _uuid

async def _load_project_by_id(session, project_id):
    pid = project_id if isinstance(project_id, _uuid.UUID) else _uuid.UUID(str(project_id))
    return (await session.execute(select(Project).where(Project.id == pid))).scalar_one_or_none()
```

Change the signature to `async def distill_score_export(*, out: str = "pack.json", mode: str = "category_sweep", project_id=None) -> dict:` and replace the project-load block:

```python
    async with sm() as session:
        proj = (await _load_project_by_id(session, project_id) if project_id is not None
                else await _load_project(session, project_name))
        if proj is None:
            who = f"id {project_id}" if project_id is not None else repr(project_name)
            raise RuntimeError(f"project {who} not seeded yet — run `lacuna seed` first")
        # ... rest unchanged: works/clusters/review_counts now scoped to proj.id
```

Everything downstream already filters by `proj.id`, so no other math changes. The pack's `project` label should use `proj.name` (not the config name) when `project_id` is given — update the `build_pack(project=...)` call to `project=proj.name`.

- [ ] **Step 4: Run to verify the param test passes**

Run: `.venv\Scripts\pytest.exe tests/export/test_distill_project_id.py -q`
Expected: PASS. Also run the existing export suite to confirm no regression:
Run: `.venv\Scripts\pytest.exe tests/export -q`
Expected: PASS (CLI path still works with `project_id=None`).

- [ ] **Step 5: Write the failing endpoint test (DB-gated)**

`tests/api/test_export.py`:

```python
import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_export_json_returns_pack(client):
    projs = (await client.get("/projects")).json()
    seeded = [p for p in projs if p["seeded"]]
    if not seeded:
        pytest.skip("no seeded project")
    pid = seeded[0]["id"]
    resp = await client.get(f"/projects/{pid}/export", params={"format": "json"})
    assert resp.status_code == 200
    pack = resp.json()
    assert "candidates" in pack
    assert "known_limitations" in pack
```

- [ ] **Step 6: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_export.py -q`
Expected: FAIL — 404.

- [ ] **Step 7: Implement the export router (id-aware)**

`api/routers/export.py`:

```python
# api/routers/export.py
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool

from lacuna.pipeline.distill import distill_score_export

router = APIRouter(prefix="/projects/{project_id}", tags=["export"])


@router.get("/export")
async def export_pack(project_id: uuid.UUID, format: str = Query("json"),
                      scope: str = Query("category_sweep")):
    """Regenerate the Context Pack for THIS project via the (id-aware) distiller ($0).
    The distiller is sync/IO-heavy → run it off the event loop. Scoped by project_id
    so two projects export their own packs (Frontend PRD §9 isolation)."""
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "pack.json")
        await run_in_threadpool(_distill_sync, out, scope, str(project_id))
        if format == "md":
            md = Path(out).with_suffix(".md").read_text(encoding="utf-8")
            return PlainTextResponse(md, media_type="text/markdown")
        pack = json.loads(Path(out).read_text(encoding="utf-8"))
        return JSONResponse(pack)


def _distill_sync(out: str, mode: str, project_id: str) -> None:
    import asyncio
    asyncio.run(distill_score_export(out=out, mode=mode, project_id=project_id))
```

- [ ] **Step 8: Register in `api/app.py`**

```python
    from api.routers import projects, reads, export
    for r in (projects, reads, export):
        app.include_router(r.router)
```

- [ ] **Step 9: Run to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/api/test_export.py -q`
Expected: PASS (regenerates the pack for the project named in the URL).

- [ ] **Step 10: Commit**

```bash
git add lacuna/pipeline/distill.py api/routers/export.py api/app.py tests/export/test_distill_project_id.py tests/api/test_export.py
git commit -m "feat(api): id-aware Context Pack export — distiller parameterized by project_id"
```

---

## W3 — Batch Seed Integration

### Task 8: Seed progress callback + `POST /seed` subprocess launcher

**Files:**
- Modify: `lacuna/seed/seed.py` (add optional `progress_cb`)
- Create: `api/routers/seed.py`
- Modify: `api/app.py` (register)
- Test: `tests/seed/test_seed_progress_cb.py`, `tests/api/test_seed_endpoint.py`

**Interfaces:**
- Produces:
  - `run_seed(..., progress_cb: Callable[[dict], None] | None = None)` — when given, called with `{"step": str, "progress_pct": float, "counts": dict}` at the existing logging points (does not change seed math).
  - `POST /projects/{id}/seed` (body `SeedRequest`) → launches `.venv\Scripts\lacuna.exe seed` as a subprocess, creates a `jobs` row (`kind='seed'`), returns `{job_id}`. The subprocess writes progress into `jobs` via a small runner.

> **Architecture (per §3.1/§13.5):** the seed is CPU-heavy + hour-long → it MUST stay a subprocess, not run in the API process. The endpoint creates the job row, then spawns a detached subprocess that updates the row. A dedicated `lacuna seed-job <job_id>` CLI subcommand wraps `run_seed` with a `progress_cb` that writes to `jobs`.

- [ ] **Step 1: Write the failing test for the callback**

`tests/seed/test_seed_progress_cb.py`:

```python
def test_run_seed_invokes_progress_cb(monkeypatch):
    """run_seed must call progress_cb at its logging points without altering counts.
    We stub the heavy internals and assert the callback sees step/progress updates."""
    from lacuna.seed import seed as seed_mod

    events = []

    def fake_build_and_persist(*a, **k):
        cb = k.get("progress_cb")
        if cb:
            cb({"step": "meta", "progress_pct": 10.0, "counts": {"meta_scanned": 25000}})
            cb({"step": "clustering", "progress_pct": 90.0, "counts": {"clusters": 2}})
        return {"clusters": 2, "works_selected": 6}

    # _run is the internal entry run_seed delegates to; adapt name to the real one.
    monkeypatch.setattr(seed_mod, "_run_seed_async", fake_build_and_persist, raising=False)
    counts = seed_mod.run_seed(rebuild=True, max_works=1, meta_limit=1, review_limit=1,
                               progress_cb=lambda e: events.append(e))
    assert any(e["step"] == "clustering" for e in events)
    assert counts["clusters"] == 2
```

> **Adapt to the real internals:** read `lacuna/seed/seed.py` first. `run_seed` currently calls into the orchestrator + `persist_seed_plan`. Thread an optional `progress_cb` parameter through `run_seed` → the orchestrator's existing progress logging points (the `[seed +Ns]` lines). Where the orchestrator emits a log line, also call `progress_cb(event)` if provided. Keep counts identical.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/seed/test_seed_progress_cb.py -q`
Expected: FAIL — `run_seed() got an unexpected keyword argument 'progress_cb'`.

- [ ] **Step 3: Thread `progress_cb` through `run_seed`**

In `lacuna/seed/seed.py`, add `progress_cb: Callable[[dict], None] | None = None` to `run_seed`'s signature and pass it down to the orchestrator's scan loop. At each existing progress log point (meta scan, review scan, per-work, clustering), emit:

```python
if progress_cb:
    progress_cb({"step": step, "progress_pct": pct, "counts": counts_so_far})
```

Compute `pct` from the existing scanned/limit ratios already present in the log strings (meta phase 0–40%, review phase 40–80%, NLP 80–100% are reasonable bands). **Do not change any seed math or counts** — only add callback emissions alongside the existing `typer`/print logging.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/seed/test_seed_progress_cb.py -q`
Expected: PASS.

- [ ] **Step 5: Add the `seed-job` CLI subcommand**

In `app/cli.py`, add a command that runs the seed and writes progress into a `jobs` row:

```python
@app.command("seed-job")
def seed_job_cmd(
    job_id: str = typer.Argument(..., help="jobs.id to report progress into"),
    max_works: int = typer.Option(25), meta_limit: int = typer.Option(200_000),
    review_limit: int = typer.Option(1_000_000),
) -> None:
    """Run a seed and stream progress into the jobs table (called by the API as a subprocess)."""
    import asyncio
    import uuid as _uuid
    from lacuna.db.session import build_sessionmaker
    from lacuna.seed.seed import run_seed
    from api import jobs as jobs_svc

    sm = build_sessionmaker()
    jid = _uuid.UUID(job_id)

    def cb(event: dict) -> None:
        asyncio.run(jobs_svc.update_job(
            sm, jid, status="running",
            progress_pct=event.get("progress_pct"), step=event.get("step"),
            counts=event.get("counts")))

    asyncio.run(jobs_svc.update_job(sm, jid, status="running", progress_pct=0, step="starting"))
    try:
        counts = run_seed(rebuild=True, max_works=max_works, meta_limit=meta_limit,
                          review_limit=review_limit, progress_cb=cb)
        asyncio.run(jobs_svc.update_job(sm, jid, status="done", progress_pct=100,
                                        counts=counts, result_ref=str(counts.get("project_id", ""))))
    except Exception as exc:  # noqa: BLE001 — record then re-raise for the subprocess exit code
        asyncio.run(jobs_svc.update_job(sm, jid, status="error", error_detail=str(exc)))
        raise
```

> Calling `asyncio.run` per event is acceptable here because the seed's progress cadence is ~60s (see `seed_run.log`), not per-row. If cadence tightens later, batch updates.

- [ ] **Step 6: Implement the `POST /seed` endpoint**

`api/routers/seed.py`:

```python
# api/routers/seed.py
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends

from api.deps import get_sessionmaker
from api.schemas import SeedRequest
from api import jobs as jobs_svc

router = APIRouter(prefix="/projects/{project_id}", tags=["seed"])

_LACUNA = str(Path(sys.prefix) / "Scripts" / "lacuna.exe")


@router.post("/seed")
async def start_seed(project_id: uuid.UUID, body: SeedRequest, sm=Depends(get_sessionmaker)):
    """Start a batch seed as a SEPARATE SUBPROCESS (Frontend PRD §3.1/§13.5). Returns
    a job id immediately; progress lands in the jobs row. Not resumable (matches the
    engine): a crash -> status='error' and the operator re-runs."""
    job_id = await jobs_svc.create_job(sm, kind="seed", project_id=project_id)
    subprocess.Popen(
        [_LACUNA, "seed-job", str(job_id),
         "--max-works", str(body.max_works),
         "--meta-limit", str(body.meta_limit),
         "--review-limit", str(body.review_limit)],
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return {"job_id": str(job_id)}
```

- [ ] **Step 7: Write the endpoint test (returns a job id; does NOT run a real seed)**

`tests/api/test_seed_endpoint.py`:

```python
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_seed_returns_job_id_without_blocking(client, monkeypatch):
    import api.routers.seed as seed_router

    spawned = {}

    class _FakePopen:
        def __init__(self, args, **kw):
            spawned["args"] = args

    monkeypatch.setattr(seed_router.subprocess, "Popen", _FakePopen)
    projs = (await client.get("/projects")).json()
    pid = projs[0]["id"] if projs else None
    if pid is None:
        pytest.skip("no project")
    resp = await client.post(f"/projects/{pid}/seed", json={"max_works": 25})
    body = resp.json()
    assert uuid.UUID(body["job_id"])
    assert "seed-job" in spawned["args"]
```

- [ ] **Step 8: Register + run**

Register in `api/app.py` (`from api.routers import ... seed`; `app.include_router(seed.router)`).
Run: `.venv\Scripts\pytest.exe tests/api/test_seed_endpoint.py tests/seed/test_seed_progress_cb.py -q`
Expected: PASS (Popen is mocked — no real hour-long seed runs in tests).

- [ ] **Step 9: Commit**

```bash
git add lacuna/seed/seed.py app/cli.py api/routers/seed.py api/app.py tests/seed/test_seed_progress_cb.py tests/api/test_seed_endpoint.py
git commit -m "feat(api): batch seed as subprocess reporting into jobs table"
```

---

### Task 9: Job status endpoints

**Files:**
- Create: `api/routers/jobs.py`
- Modify: `api/app.py` (register)
- Test: `tests/api/test_jobs.py`

**Interfaces:**
- Produces: `GET /jobs/{id}` → `JobOut`; `GET /projects/{id}/jobs` → `list[JobOut]`.

- [ ] **Step 1: Write the failing test (DB-gated)**

`tests/api/test_jobs.py`:

```python
import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_get_job_404_for_unknown(client):
    import uuid
    resp = await client.get(f"/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_cancel_marks_running_job_cancelled(client):
    from lacuna.db.session import build_sessionmaker
    from api import jobs as jobs_svc
    sm = build_sessionmaker()
    jid = await jobs_svc.create_job(sm, kind="live_search", project_id=None)
    await jobs_svc.update_job(sm, jid, status="running", progress_pct=20)
    resp = await client.post(f"/jobs/{jid}/cancel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error" and body["error_detail"] == "cancelled"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_jobs.py -q`
Expected: FAIL — route returns 404 from the router-not-found path, but with the wrong shape (no route). After implementing, the 404 is the explicit `HTTPException`.

- [ ] **Step 3: Implement the jobs router**

`api/routers/jobs.py`:

```python
# api/routers/jobs.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_sessionmaker
from api.schemas import JobOut
from api import jobs as jobs_svc

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    row = await jobs_svc.get_job(sm, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return row


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    """Cancel a running job (Frontend PRD §11). The `jobs` CHECK constraint allows
    only queued/running/done/error (no schema change, §13.12), so cancellation is
    recorded as status='error' with error_detail='cancelled' — the UI renders that
    marker as 'Cancelled', not a failure. The UI stops polling on this terminal state.
    For live_search (seconds) this primarily halts UI polling + marks the row; the
    in-flight threadpool task is allowed to finish (no hard mid-NLP kill in v1)."""
    row = await jobs_svc.get_job(sm, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    if row["status"] in ("done", "error"):
        return row  # already terminal — idempotent
    await jobs_svc.update_job(sm, job_id, status="error", error_detail="cancelled")
    return await jobs_svc.get_job(sm, job_id)


@router.get("/projects/{project_id}/jobs", response_model=list[JobOut])
async def list_project_jobs(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    return await jobs_svc.list_jobs(sm, project_id)
```

- [ ] **Step 4: Register + run**

Register in `api/app.py`. Run: `.venv\Scripts\pytest.exe tests/api/test_jobs.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/routers/jobs.py api/app.py tests/api/test_jobs.py
git commit -m "feat(api): job status + cancel endpoints"
```

---

### Task 9b: `POST /sweep` — category sweep as a job

**Files:**
- Create: `api/routers/sweep.py`
- Modify: `api/app.py` (register)
- Test: `tests/api/test_sweep_endpoint.py`

**Interfaces:**
- Consumes: the id-aware `distill_score_export(mode="category_sweep", project_id=...)` (Task 7), jobs service.
- Produces: `POST /projects/{id}/sweep` → creates a `jobs` row (`kind='sweep'`), runs the distiller **off the event loop**, persists scores, marks the job done; returns `{job_id}`. Results read via `GET /candidates` (Task 6). The sweep is corpus-only and $0 (reads seeded data; no hour-long scan), so it runs in a threadpool like export — NOT a subprocess like seed.

- [ ] **Step 1: Write the failing test (DB-gated)**

`tests/api/test_sweep_endpoint.py`:

```python
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_sweep_runs_as_job_and_completes(client):
    projs = (await client.get("/projects")).json()
    seeded = [p for p in projs if p["seeded"]]
    if not seeded:
        pytest.skip("no seeded project")
    pid = seeded[0]["id"]
    resp = await client.post(f"/projects/{pid}/sweep")
    job_id = resp.json()["job_id"]
    assert uuid.UUID(job_id)
    job = (await client.get(f"/jobs/{job_id}")).json()
    assert job["status"] in ("running", "done")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_sweep_endpoint.py -q`
Expected: FAIL — 404.

- [ ] **Step 3: Implement the sweep router**

`api/routers/sweep.py`:

```python
# api/routers/sweep.py
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from api.deps import get_sessionmaker
from api import jobs as jobs_svc
from lacuna.pipeline.distill import distill_score_export

router = APIRouter(prefix="/projects/{project_id}", tags=["sweep"])


@router.post("/sweep")
async def start_sweep(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    """Category Sweep (Frontend PRD §11) as a job. Corpus-only, $0 — reads seeded
    data + persists scores; no live source, no hour-long scan. Runs off the event
    loop. Results via GET /candidates."""
    job_id = await jobs_svc.create_job(sm, kind="sweep", project_id=project_id)
    await jobs_svc.update_job(sm, job_id, status="running", progress_pct=10, step="scoring")

    def _run() -> dict:
        import asyncio
        with tempfile.TemporaryDirectory() as d:
            out = str(Path(d) / "pack.json")
            return asyncio.run(distill_score_export(
                out=out, mode="category_sweep", project_id=str(project_id)))

    try:
        counts = await run_in_threadpool(_run)
        await jobs_svc.update_job(sm, job_id, status="done", progress_pct=100, counts=counts)
    except Exception as exc:  # noqa: BLE001
        await jobs_svc.update_job(sm, job_id, status="error", error_detail=str(exc))
    return {"job_id": str(job_id)}
```

- [ ] **Step 4: Register + run**

Register in `api/app.py`. Run: `.venv\Scripts\pytest.exe tests/api/test_sweep_endpoint.py -q`
Expected: PASS (runs the corpus-only distiller for the seeded project as a job).

- [ ] **Step 5: Commit**

```bash
git add api/routers/sweep.py api/app.py tests/api/test_sweep_endpoint.py
git commit -m "feat(api): POST /sweep category-sweep job (corpus-only, off event loop)"
```

---

## W4 — Live Single-Title Path (NEW glue) — **THE GATE**

> Per Frontend PRD §16: **W4 must work against a real title before any dependent UI (W6 Search) is built.** Plan B does not start until Task 12 passes.

### Task 10: `live_single_title.py` orchestrator (offline, fakes)

**Files:**
- Create: `lacuna/pipeline/live_single_title.py`
- Test: `tests/pipeline/test_live_single_title.py`

**Interfaces:**
- Consumes: `HardcoverClient.fetch_book_by_title` (returns `HardcoverBook{id,title,reviews:[HardcoverReview{rating,body,created_at}]}`), `Embedder.encode`, `cluster_embeddings` + `members_by_cluster`, `AspectLabeler.label_cluster`, `merge_clusters`/`agreement_pct`/`AspectClusterIn`, `build_pack`/`to_markdown`/`Candidate`/`Complaint`.
- Produces:
  ```python
  async def analyze_live(
      *, title: str, hardcover, embedder, labeler,
      seeded_clusters: list[AspectClusterIn] | None = None,
      cluster_min_size: int = 2, review_limit: int = 50,
      progress_cb=None,
  ) -> dict
  ```
  Returns `{"title", "fresh_only": bool, "review_count": int, "clusters": [...], "agreement_pct": float, "pack": dict}`. **Pure composition** — every heavy component is injected, so the test runs with fakes and no network/models (CLAUDE.md §3 by construction).

- [ ] **Step 1: Write the failing offline test**

`tests/pipeline/test_live_single_title.py`:

```python
import numpy as np

from lacuna.aggregation.cross_platform import AspectClusterIn
from lacuna.nlp.aspects import AspectResult
from lacuna.pipeline.live_single_title import analyze_live


class FakeHardcoverReview:
    def __init__(self, rating, body, created_at=None):
        self.rating = rating; self.body = body; self.created_at = created_at


class FakeHardcoverBook:
    def __init__(self, title, reviews):
        self.id = 1; self.title = title; self.reviews = reviews


class FakeHardcover:
    def __init__(self, book):
        self._book = book
    async def fetch_book_by_title(self, title, *, review_limit=50):
        return self._book
    async def aclose(self):
        pass


class FakeEmbedder:
    def encode(self, texts):
        # cluster by length parity so 2 clear groups form
        return np.array([[float(len(t) % 2), float(len(t)), 0.0, 0.0] for t in texts])


class FakeLabeler:
    def label_cluster(self, texts, candidate_labels=None):
        return AspectResult(label="outdated", score=0.9,
                            representative="Readers say the material feels outdated.")


async def test_live_analysis_fresh_only_builds_pack():
    book = FakeHardcoverBook("Some Title", [
        FakeHardcoverReview(2, "the examples are outdated and old"),
        FakeHardcoverReview(1, "outdated material throughout the book"),
        FakeHardcoverReview(2, "felt dated and behind the times now"),
    ])
    result = await analyze_live(
        title="Some Title", hardcover=FakeHardcover(book),
        embedder=FakeEmbedder(), labeler=FakeLabeler(),
        seeded_clusters=None, cluster_min_size=2)
    assert result["fresh_only"] is True
    assert result["review_count"] == 3
    assert "candidates" in result["pack"]
    assert result["agreement_pct"] == 0.0  # single platform -> no cross-platform agreement


async def test_live_analysis_merges_with_seeded_raises_agreement():
    book = FakeHardcoverBook("Seeded Title", [
        FakeHardcoverReview(2, "the examples are outdated and old"),
        FakeHardcoverReview(1, "outdated material throughout the book"),
    ])
    seeded = [AspectClusterIn(label="outdated", platform="amazon_corpus",
                              reviewer_count=40, helpful_weight=12.0, member_count=44)]
    result = await analyze_live(
        title="Seeded Title", hardcover=FakeHardcover(book),
        embedder=FakeEmbedder(), labeler=FakeLabeler(),
        seeded_clusters=seeded, cluster_min_size=2)
    assert result["fresh_only"] is False
    # the merged "outdated" cluster now spans hardcover + amazon_corpus
    assert any(c.get("cross_platform") for c in result["clusters"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/pipeline/test_live_single_title.py -q`
Expected: FAIL — `ModuleNotFoundError: lacuna.pipeline.live_single_title`.

- [ ] **Step 3: Implement the live glue**

`lacuna/pipeline/live_single_title.py`:

```python
# lacuna/pipeline/live_single_title.py
"""Live single-title analysis (Frontend PRD §3.2) — NEW glue composing EXISTING
components. Distinct from the batch seed and from the corpus-only single_title path.

Flow: resolve+pull title from Hardcover (live, seconds) -> embed + HDBSCAN cluster
the fresh reviews with the WARM models -> label each cluster (paraphrase only) ->
if seeded corpus clusters exist for the title, merge via cross_platform (agreement
raises confidence) -> score + build a Context Pack. The corpus is NEVER scanned here
(§1.2 HARD RULE): only Hardcover is called live.

Every heavy component is injected so this is unit-testable offline and so the API
passes its WARM singleton in (models never reload per request, §13.4). No raw review
text leaves the machine — clustering/labeling are local; the pack carries paraphrases
only (CLAUDE.md §3)."""
from __future__ import annotations

import datetime as dt

from lacuna.aggregation.cross_platform import (
    AspectClusterIn, MergedCluster, agreement_pct, merge_clusters,
)
from lacuna.export.context_pack import Candidate, Complaint, build_pack, to_markdown
from lacuna.nlp.clustering import cluster_embeddings, members_by_cluster


def _sentiment(rating: float | None) -> float:
    """rating 1->-1.0 .. 5->+1.0, clamped; mirrors the seed's proxy."""
    if rating is None:
        return 0.0
    return max(-1.0, min(1.0, (float(rating) - 3.0) / 2.0))


async def analyze_live(*, title: str, hardcover, embedder, labeler,
                       seeded_clusters: list[AspectClusterIn] | None = None,
                       cluster_min_size: int = 2, review_limit: int = 50,
                       progress_cb=None) -> dict:
    def _tick(step, pct):
        if progress_cb:
            progress_cb({"step": step, "progress_pct": pct})

    _tick("resolving", 10.0)
    book = await hardcover.fetch_book_by_title(title, review_limit=review_limit)
    if book is None:
        return {"title": title, "fresh_only": seeded_clusters is None, "review_count": 0,
                "clusters": [], "agreement_pct": 0.0, "not_found": True,
                "pack": build_pack(project=title, bisac=[], mode="single_title",
                                   generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                                   platforms_used=[], total_reviews=0,
                                   cross_platform_agreement_pct=0.0, candidates=[], max_candidates=15)}

    # Only critical reviews carry dissatisfaction signal (rating <= 3), mirroring the seed.
    crit = [r for r in book.reviews if (r.rating is None or float(r.rating) <= 3) and (r.body or "").strip()]
    texts = [r.body for r in crit]
    review_count = len(book.reviews)

    _tick("embedding", 40.0)
    fresh_clusters: list[AspectClusterIn] = []
    fresh_dicts: list[dict] = []
    if len(texts) >= cluster_min_size:
        embeds = embedder.encode(texts)
        labels = cluster_embeddings(embeds, min_cluster_size=cluster_min_size)
        _tick("labeling", 70.0)
        for _cid, idxs in members_by_cluster(labels).items():
            members = [texts[i] for i in idxs]
            res = labeler.label_cluster(members)
            reviewer_count = len(idxs)
            helpful = 0.0  # Hardcover has no helpful-vote signal
            fresh_clusters.append(AspectClusterIn(
                label=res.label, platform="hardcover", reviewer_count=reviewer_count,
                helpful_weight=helpful, member_count=reviewer_count))
            fresh_dicts.append({"label": res.label, "representative": res.representative,
                                "reviewer_count": reviewer_count, "platforms": ["hardcover"],
                                "cross_platform": False})

    # Merge with seeded corpus clusters if the title was seeded; else fresh-only.
    fresh_only = not seeded_clusters
    all_in = list(fresh_clusters) + list(seeded_clusters or [])
    _tick("merging", 85.0)
    merged: list[MergedCluster] = merge_clusters(
        all_in, embedder=embedder.encode, threshold=0.75) if all_in else []
    agreement = agreement_pct(merged, top_n=15)

    cluster_view = [{"label": m.label, "representative": m.label,
                     "reviewer_count": m.reviewer_count, "platforms": list(m.platforms),
                     "cross_platform": m.cross_platform} for m in merged] or fresh_dicts

    # Build a single-candidate pack for this title from the merged complaints.
    _tick("exporting", 95.0)
    complaints = [Complaint(aspect=m.label, reviewer_count=m.reviewer_count,
                            helpful_weight=m.helpful_weight, platforms=list(m.platforms),
                            cross_platform=m.cross_platform)
                  for m in sorted(merged, key=lambda c: c.reviewer_count, reverse=True)[:5]]
    cand = Candidate(
        ref="work", title_or_subject=book.title, gap_score=0.0, demand=0.0,
        supply_scarcity=0.0, unmet_need=0.0,
        confidence=min(1.0, 0.2 + 0.1 * len(merged) + (0.3 if not fresh_only else 0.0)),
        sample_size=len(texts),
        platforms=sorted({p for m in merged for p in m.platforms}) or ["hardcover"],
        oldest_signal=None, newest_signal=None,
        incomplete=fresh_only, blind_spot=len(texts) < 5, recent_supply_surge=False,
        top_complaints=complaints, demand_evidence={})
    pack = build_pack(
        project=book.title, bisac=[], mode="single_title",
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        platforms_used=cand.platforms, total_reviews=len(texts),
        cross_platform_agreement_pct=round(agreement, 3), candidates=[cand], max_candidates=15)

    _tick("done", 100.0)
    return {"title": book.title, "fresh_only": fresh_only, "review_count": review_count,
            "clusters": cluster_view, "agreement_pct": round(agreement, 3), "pack": pack}
```

> **`datetime.now` note:** the engine's own `distill.py` uses `dt.datetime.now(dt.timezone.utc)`, so this matches the codebase. (Only *workflow scripts* forbid `Date.now()`; normal Python is fine.)

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/pipeline/test_live_single_title.py -q`
Expected: PASS — both fresh-only and merged-with-seeded cases.

- [ ] **Step 5: Commit**

```bash
git add lacuna/pipeline/live_single_title.py tests/pipeline/test_live_single_title.py
git commit -m "feat(engine): live single-title glue (Frontend PRD §3.2) — offline-tested"
```

---

### Task 11: `POST /search` — wire live analysis as a job

**Files:**
- Create: `api/routers/search.py`
- Modify: `api/app.py` (register)
- Test: `tests/api/test_search_endpoint.py`

**Interfaces:**
- Consumes: `analyze_live` (Task 10), `EngineRuntime` (warm models), `HardcoverClient`, jobs service, `Settings.hardcover_api_token`.
- Produces: `POST /projects/{id}/search` (body `SearchRequest`) → creates a `jobs` row (`kind='live_search'`), runs `analyze_live` **off the event loop** (`run_in_threadpool`) using the warm runtime, writes the result into the job (`result_ref` + `counts`), returns `{job_id}`. The UI polls `GET /jobs/{id}`. Looks up any seeded work with a matching normalized key in this project to pass `seeded_clusters`.

- [ ] **Step 1: Write the failing test (mocks Hardcover + uses fake runtime)**

`tests/api/test_search_endpoint.py`:

```python
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_search_creates_job_and_runs_live(client, monkeypatch):
    import api.routers.search as search_router

    class _FakeReview:
        def __init__(self, rating, body):
            self.rating = rating; self.body = body; self.created_at = None

    class _FakeBook:
        id = 1; title = "Mocked"
        reviews = [_FakeReview(2, "outdated examples"), _FakeReview(1, "dated content here")]

    class _FakeHC:
        def __init__(self, *a, **k): pass
        async def fetch_book_by_title(self, title, *, review_limit=50): return _FakeBook()
        async def aclose(self): pass

    monkeypatch.setattr(search_router, "HardcoverClient", _FakeHC)
    monkeypatch.setattr(search_router, "_hardcover_token", lambda: "fake-token")

    projs = (await client.get("/projects")).json()
    pid = projs[0]["id"] if projs else None
    if pid is None:
        pytest.skip("no project")
    resp = await client.post(f"/projects/{pid}/search", json={"title": "Mocked"})
    job_id = resp.json()["job_id"]
    assert uuid.UUID(job_id)

    # job should resolve to done with the live result (search is seconds)
    job = (await client.get(f"/jobs/{job_id}")).json()
    assert job["status"] in ("running", "done")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/api/test_search_endpoint.py -q`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Implement the search router**

`api/routers/search.py`:

```python
# api/routers/search.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from api.deps import get_runtime, get_sessionmaker
from api.schemas import SearchRequest
from api import jobs as jobs_svc
from lacuna.adapters.hardcover import HardcoverClient
from lacuna.aggregation.cross_platform import AspectClusterIn
from lacuna.config import get_settings
from lacuna.db.models import AspectCluster, Work
from lacuna.pipeline.live_single_title import analyze_live
from lacuna.seed.normalization import normalize_title  # adapt to the real normalizer name

router = APIRouter(prefix="/projects/{project_id}", tags=["search"])


def _hardcover_token() -> str | None:
    return get_settings().hardcover_api_token


async def _seeded_clusters_for(sm, project_id: uuid.UUID, title: str) -> list[AspectClusterIn]:
    """If a seeded work matches this title, return its clusters as merge inputs; else []."""
    async with sm() as session:
        works = (await session.execute(
            select(Work).where(Work.project_id == project_id))).scalars().all()
        key = normalize_title(title)  # adapt: use the same normalization the seed used
        match = next((w for w in works if w.normalized_key == key), None)
        if match is None:
            return []
        cls = (await session.execute(
            select(AspectCluster).where(AspectCluster.work_id == match.id))).scalars().all()
        return [AspectClusterIn(label=c.label, platform=(c.platforms[0] if c.platforms else "amazon_corpus"),
                                reviewer_count=c.reviewer_count, helpful_weight=float(c.helpful_weight or 0.0),
                                member_count=c.member_count) for c in cls]


@router.post("/search")
async def start_search(project_id: uuid.UUID, body: SearchRequest,
                       sm=Depends(get_sessionmaker), runtime=Depends(get_runtime)):
    """Live single-title search (Frontend PRD §3.2). Hardcover ONLY — never the corpus
    (§1.2). Runs as a job for consistent UX; the heavy NLP runs off the event loop
    with the WARM models."""
    if not body.title and not body.isbn:
        raise HTTPException(status_code=422, detail="title or isbn required")
    token = _hardcover_token()
    if not token:
        raise HTTPException(status_code=503, detail="HARDCOVER_API_TOKEN not configured on the backend")

    job_id = await jobs_svc.create_job(sm, kind="live_search", project_id=project_id)
    title = body.title or body.isbn
    seeded = await _seeded_clusters_for(sm, project_id, title)

    await jobs_svc.update_job(sm, job_id, status="running", progress_pct=5, step="resolving")
    client = HardcoverClient(token=token)
    try:
        def _run():
            import asyncio
            return asyncio.run(analyze_live(
                title=title, hardcover=client, embedder=runtime.embedder,
                labeler=runtime.labeler, seeded_clusters=seeded or None))
        result = await run_in_threadpool(_run)
        await jobs_svc.update_job(
            sm, job_id, status="done", progress_pct=100,
            counts={"review_count": result["review_count"], "fresh_only": result["fresh_only"],
                    "agreement_pct": result["agreement_pct"], "clusters": result["clusters"],
                    "pack": result["pack"]})
    except Exception as exc:  # noqa: BLE001
        await jobs_svc.update_job(sm, job_id, status="error", error_detail=str(exc))
    finally:
        await run_in_threadpool(lambda: __import__("asyncio").run(client.aclose()))

    return {"job_id": str(job_id)}
```

> **Adapt the normalizer:** read `lacuna/seed/normalization.py` and use the exact function/version the seed used to build `normalized_key`, so the seeded-match lookup is correct. If normalization needs `norm_version`, replicate the seed's call.

- [ ] **Step 4: Register + run**

Register in `api/app.py`. Run: `.venv\Scripts\pytest.exe tests/api/test_search_endpoint.py -q`
Expected: PASS (Hardcover mocked, fake warm runtime, real DB for the job row).

- [ ] **Step 5: Commit**

```bash
git add api/routers/search.py api/app.py tests/api/test_search_endpoint.py
git commit -m "feat(api): POST /search live single-title job (Hardcover-only, off event loop)"
```

---

### Task 12: **W4 GATE** — prove live search on a real title

**Files:**
- Create: `tests/test_live_search_gate.py`

**Interfaces:**
- Consumes: the real `HardcoverClient` + real warm models + `analyze_live`. Gated on `HARDCOVER_API_TOKEN` (mirrors `tests/test_hardcover_live.py`).

> This is the gate that mirrors the engine's G0. **It loads the real models and calls the live Hardcover API.** It is slow and skipped in CI when the token is absent — but it MUST be run manually and pass before Plan B (W5+) begins.

- [ ] **Step 1: Write the gate test**

`tests/test_live_search_gate.py`:

```python
import os

import pytest

from lacuna.adapters.hardcover import HardcoverClient
from lacuna.config import get_settings
from lacuna.nlp.aspects import AspectLabeler
from lacuna.nlp.embeddings import Embedder
from lacuna.pipeline.live_single_title import analyze_live

pytestmark = pytest.mark.skipif(
    not os.getenv("HARDCOVER_API_TOKEN"),
    reason="HARDCOVER_API_TOKEN not set — W4 live gate skipped",
)


async def test_live_search_produces_real_result_for_known_title():
    """W4 GATE (Frontend PRD §16): a live, fresh-only analysis of a real, popular
    title must return reviews and a Context Pack in seconds — proving the product
    needs no pre-seed. Uses the REAL Hardcover API + REAL local models."""
    token = get_settings().hardcover_api_token
    client = HardcoverClient(token=token)
    try:
        result = await analyze_live(
            title="Atomic Habits", hardcover=client,
            embedder=Embedder(), labeler=AspectLabeler(), seeded_clusters=None)
    finally:
        await client.aclose()

    assert result.get("not_found") is not True, "Hardcover did not resolve a known title"
    assert result["review_count"] > 0, "no live reviews returned"
    assert "candidates" in result["pack"]
    assert result["fresh_only"] is True
    # Provenance honesty: fresh-only must be flagged incomplete in the pack.
    assert result["pack"]["candidates"][0]["validity"]["incomplete"] is True
```

- [ ] **Step 2: Run the gate (manually, with the token set)**

Set the token in `.env` (already present per the engine), then:
Run: `.venv\Scripts\pytest.exe tests/test_live_search_gate.py -q -s`
Expected: PASS — prints/returns >0 live reviews and a built pack. **If it fails, stop and debug the live path before any frontend work** (per §16 + `CLAUDE.md` §2). Likely causes to check: Hardcover token rotation, the `search`→`user_books` query shape, model revisions pinned (`scripts/pin_revisions.py`).

- [ ] **Step 3: Smoke-run the full backend end-to-end (manual)**

```bash
.venv\Scripts\uvicorn.exe api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Then in another shell verify the live path over HTTP against a real project + title:
- `GET http://127.0.0.1:8000/health` → `{"models_ready": true}` after warm-up.
- `POST http://127.0.0.1:8000/projects/<seeded-id>/search` body `{"title":"Atomic Habits"}` → `{job_id}`.
- Poll `GET http://127.0.0.1:8000/jobs/<job_id>` → `status` reaches `done` within seconds, `counts.review_count > 0`.
- Confirm (per acceptance §4) the corpus was NOT scanned: the call completes in seconds and only Hardcover was hit.

- [ ] **Step 4: Commit + tag the gate pass**

```bash
git add tests/test_live_search_gate.py
git commit -m "test(api): W4 live-search gate — proven on a real title"
```

Record the gate pass (date + title + review count) in `docs/METHODOLOGY.md` so Plan B can start with the gate green.

---

## Self-Review (against Frontend PRD §4 / §13 / §16)

- **§4 endpoints:** projects CRUD + **PUT** (T5), seed (T8), search + works-query (T11/T6), **sweep job** (T9b) + candidates read (T6 `/candidates`), reads (T6), **id-aware export** (T7), jobs + **cancel** (T9), `/health` + CORS + warm models (T2/T3). ✅ — all §4 endpoints covered; the three folded-in additions (PUT, cancel, sweep job) are in T5/T9/T9b, and export is now `project_id`-scoped (T7) so multi-project isolation holds (§9).
- **§13.1 reuse:** every router delegates to engine functions; only new code is `live_single_title.py`. ✅
- **§13.2 corpus≠live:** `/search` calls Hardcover only (T11); seed is the only corpus path (T8, subprocess). ✅
- **§13.4 warm models:** T2/T3 load once in lifespan; `/search` uses `runtime.*`. ✅
- **§13.5 off-loop:** export + search use `run_in_threadpool`; seed is a subprocess. ✅
- **§13.6 one job system:** all async work → `jobs` (T1/T4/T8/T9/T11). ✅
- **§13.7 no secrets:** DTOs never include keys; token only read server-side (T11). ✅
- **§13.12 schema:** only `jobs` added (T1). ✅
- **§16 gate:** T12 proves live on a real title before Plan B. ✅
- **Placeholder scan:** two tasks (T8 callback wiring, T11 normalizer) say "adapt to the real internals" — these are explicit instructions to read one named file and match an existing signature, not vague TODOs. Flagged inline.

---

*Backend done when Task 12 (W4 gate) is green against a real title. Then proceed to Plan B (W5→W8).*
