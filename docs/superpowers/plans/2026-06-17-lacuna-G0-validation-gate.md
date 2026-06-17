# Workstream G0 — Hardcover Validation Gate — Implementation Plan ⛔

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **⛔ HARD GATE (PRD §18, CLAUDE.md §4):** The historical fusion and scoring layers (F, G, H) MUST NOT be built or run until `lacuna validate-hardcover` passes against the live API. If this gate fails, STOP and report — do not proceed to C/E/D/F/G/H. A failure here means the "fresh sentiment" layer assumption is wrong and the downstream design must change.

**Goal:** Implement `lacuna validate-hardcover` — fetch a real title via the live Hardcover API, confirm live review availability, and log the outcome to `analysis_runs (mode='validation')` — and gate the build on it passing.

**Architecture:** A dependency-injected `validate_hardcover()` in `lacuna/pipeline/validation.py` runs the Hardcover adapter against a known-popular title, counts returned reviews, and records an `analysis_runs` row via a recorder callable (DB writer by default, fake in tests). A Typer CLI (`app/cli.py`) wraps it and exits non-zero on failure so CI / the build sequence can branch on it. A `skipif`-guarded live contract test exercises the real API when a token is present.

**Tech Stack:** Typer, SQLAlchemy async (AnalysisRun model from A), the Hardcover adapter from B, pytest.

**Depends on:** A (config, models, session), B (Hardcover adapter). **Blocks:** F, G, H (and therefore I, J's full pass).

---

### Task G0.1: Validation logic (`lacuna/pipeline/validation.py`)

**Files:**
- Create: `lacuna/pipeline/__init__.py`
- Create: `lacuna/pipeline/validation.py`
- Test: `tests/test_validation.py`

- [ ] **Step 1: Write the failing test** (fake client + list recorder — no network, no DB)

```python
# tests/test_validation.py
import pytest
from lacuna.pipeline.validation import validate_hardcover, ValidationResult

class FakeBook:
    def __init__(self, title, reviews): self.title = title; self.reviews = reviews

class FakeClient:
    def __init__(self, book): self._book = book
    async def fetch_book_by_title(self, title): return self._book
    async def aclose(self): pass

async def test_gate_passes_when_reviews_present():
    recorded = []
    async def recorder(res): recorded.append(res)
    client = FakeClient(FakeBook("Atomic Habits", [object(), object(), object()]))
    res = await validate_hardcover(client, sample_title="Atomic Habits", recorder=recorder)
    assert isinstance(res, ValidationResult)
    assert res.passed is True and res.review_count == 3
    assert recorded and recorded[0].passed is True

async def test_gate_fails_when_no_reviews():
    client = FakeClient(FakeBook("Atomic Habits", []))
    res = await validate_hardcover(client, sample_title="Atomic Habits", recorder=None)
    assert res.passed is False and res.review_count == 0

async def test_gate_fails_when_title_not_found():
    client = FakeClient(None)
    res = await validate_hardcover(client, sample_title="Nonexistent", recorder=None)
    assert res.passed is False and res.error is not None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_validation.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/pipeline/__init__.py` (empty) and `lacuna/pipeline/validation.py`**

```python
# lacuna/pipeline/validation.py
"""G0 hard gate: confirm Hardcover returns live reviews for a real title."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class ValidationResult:
    passed: bool
    title: str
    review_count: int
    error: str | None = None


async def validate_hardcover(
    client,
    *,
    sample_title: str = "Atomic Habits",
    recorder: Callable[[ValidationResult], Awaitable[None]] | None = None,
) -> ValidationResult:
    """Fetch a real title and confirm >0 live reviews. Records via `recorder`."""
    try:
        book = await client.fetch_book_by_title(sample_title)
        if book is None:
            result = ValidationResult(False, sample_title, 0,
                                      error=f"title not found on Hardcover: {sample_title!r}")
        else:
            count = len(book.reviews)
            result = ValidationResult(
                passed=count > 0, title=book.title, review_count=count,
                error=None if count > 0 else "title found but no live reviews available",
            )
    except Exception as exc:  # noqa: BLE001  (gate must capture, not crash)
        result = ValidationResult(False, sample_title, 0, error=f"{type(exc).__name__}: {exc}")

    if recorder is not None:
        await recorder(result)
    return result
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_validation.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/pipeline/__init__.py lacuna/pipeline/validation.py tests/test_validation.py
git commit -m "feat: G0 Hardcover validation logic (DI, no network in tests)"
```

---

### Task G0.2: DB recorder — log to `analysis_runs (mode='validation')`

**Files:**
- Modify: `lacuna/pipeline/validation.py` (add `make_db_recorder`)
- Test: `tests/test_validation_recorder.py`

- [ ] **Step 1: Write the failing test** (capture the AnalysisRun built, using a fake session)

```python
# tests/test_validation_recorder.py
from lacuna.pipeline.validation import make_db_recorder, ValidationResult
from lacuna.db.models import AnalysisRun

class FakeSession:
    def __init__(self, sink): self._sink = sink
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    def add(self, obj): self._sink.append(obj)
    async def commit(self): pass

def fake_sessionmaker(sink):
    def _mk(): return FakeSession(sink)
    return _mk

async def test_recorder_writes_validation_run():
    sink = []
    recorder = make_db_recorder(sessionmaker=fake_sessionmaker(sink))
    await recorder(ValidationResult(True, "Atomic Habits", 12))
    assert len(sink) == 1
    run = sink[0]
    assert isinstance(run, AnalysisRun)
    assert run.mode == "validation"
    assert run.status == "ok"
    assert run.counts == {"review_count": 12}
    assert run.target == "Atomic Habits"

async def test_recorder_marks_error_status():
    sink = []
    recorder = make_db_recorder(sessionmaker=fake_sessionmaker(sink))
    await recorder(ValidationResult(False, "X", 0, error="no live reviews"))
    assert sink[0].status == "error"
    assert sink[0].error_detail == "no live reviews"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_validation_recorder.py -v`
Expected: FAIL — `cannot import name 'make_db_recorder'`.

- [ ] **Step 3: Add `make_db_recorder` to `lacuna/pipeline/validation.py`**

Append to the file:

```python
import datetime as _dt

from lacuna.db.models import AnalysisRun
from lacuna.db.session import build_sessionmaker


def make_db_recorder(sessionmaker=None):
    """Return an async recorder that writes a validation row to analysis_runs."""
    maker = sessionmaker or build_sessionmaker()

    async def _record(result: ValidationResult) -> None:
        run = AnalysisRun(
            project_id=None,
            mode="validation",
            target=result.title,
            sources_used=["hardcover"],
            finished_at=_dt.datetime.now(_dt.timezone.utc),
            status="ok" if result.passed else "error",
            counts={"review_count": result.review_count},
            error_detail=result.error,
        )
        async with maker() as session:
            session.add(run)
            await session.commit()

    return _record
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_validation_recorder.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/pipeline/validation.py tests/test_validation_recorder.py
git commit -m "feat: analysis_runs(mode=validation) DB recorder for G0"
```

---

### Task G0.3: Typer CLI command (`app/cli.py`)

**Files:**
- Create: `app/__init__.py`
- Create: `app/cli.py`
- Test: `tests/test_cli_validate.py`

- [ ] **Step 1: Write the failing test** (CliRunner; monkeypatch the validation to avoid network)

```python
# tests/test_cli_validate.py
from typer.testing import CliRunner
import app.cli as cli
from lacuna.pipeline.validation import ValidationResult

runner = CliRunner()

def test_validate_command_exits_zero_on_pass(monkeypatch):
    # _run_validation is sync (it wraps asyncio.run internally), so a plain lambda suffices.
    monkeypatch.setattr(cli, "_run_validation", lambda: ValidationResult(True, "Atomic Habits", 9))
    result = runner.invoke(cli.app, ["validate-hardcover"])
    assert result.exit_code == 0
    assert "PASS" in result.stdout

def test_validate_command_exits_one_on_fail(monkeypatch):
    monkeypatch.setattr(cli, "_run_validation", lambda: ValidationResult(False, "X", 0, error="no live reviews"))
    result = runner.invoke(cli.app, ["validate-hardcover"])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_cli_validate.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `app/__init__.py` (empty) and `app/cli.py`**

```python
# app/cli.py
"""Lacuna CLI. G0 ships `validate-hardcover`; later workstreams add seed/analyze/sweep/export."""
from __future__ import annotations

import asyncio

import typer

from lacuna.config import get_settings
from lacuna.adapters.hardcover import HardcoverClient
from lacuna.pipeline.validation import (
    ValidationResult, make_db_recorder, validate_hardcover,
)

app = typer.Typer(help="Lacuna — reader-dissatisfaction gap engine", no_args_is_help=True)


def _run_validation() -> ValidationResult:
    """Build the live client + DB recorder and run the gate. Patched in tests."""
    settings = get_settings()
    if not settings.hardcover_api_token:
        return ValidationResult(False, "(none)", 0, error="HARDCOVER_API_TOKEN not set in .env")

    async def _go() -> ValidationResult:
        client = HardcoverClient(token=settings.hardcover_api_token)
        try:
            return await validate_hardcover(client, recorder=make_db_recorder())
        finally:
            await client.aclose()

    return asyncio.run(_go())


@app.command("validate-hardcover")
def validate_hardcover_cmd() -> None:
    """G0 gate: confirm the Hardcover API returns live reviews for a real title."""
    result = _run_validation()
    if result.passed:
        typer.secho(f"PASS — {result.title!r}: {result.review_count} live reviews", fg=typer.colors.GREEN)
        raise typer.Exit(code=0)
    typer.secho(f"FAIL — {result.error}", fg=typer.colors.RED)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_cli_validate.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/cli.py tests/test_cli_validate.py
git commit -m "feat: 'lacuna validate-hardcover' CLI (exit code gates the build)"
```

---

### Task G0.4: Live Hardcover contract test (the §15 live-availability check)

**Files:**
- Create: `tests/test_hardcover_live.py`

> PRD §15/§17.2/§17.13: a live-availability check. Guarded by `skipif` so the unit suite stays offline/$0; runs only when `HARDCOVER_API_TOKEN` is set.

- [ ] **Step 1: Write the live test**

```python
# tests/test_hardcover_live.py
import os
import pytest
from lacuna.config import get_settings
from lacuna.adapters.hardcover import HardcoverClient
from lacuna.pipeline.validation import validate_hardcover

pytestmark = pytest.mark.skipif(
    not os.getenv("HARDCOVER_API_TOKEN"),
    reason="HARDCOVER_API_TOKEN not set — live gate skipped",
)

async def test_hardcover_returns_live_reviews_for_known_title():
    token = get_settings().hardcover_api_token
    client = HardcoverClient(token=token)
    try:
        res = await validate_hardcover(client, sample_title="Atomic Habits", recorder=None)
    finally:
        await client.aclose()
    assert res.passed, f"G0 gate failed: {res.error}"
    assert res.review_count > 0
```

- [ ] **Step 2: Run it (with token in env)**

Run: `uv run pytest tests/test_hardcover_live.py -v`
Expected (token set): 1 passed. (token unset): 1 skipped.

> **If this test fails with the token set:** the Hardcover GraphQL field names or review availability differ from the assumption in Task B3. Fix the query in `lacuna/adapters/hardcover.py` (the single change point) and re-run. Do **not** proceed past the gate until green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_hardcover_live.py
git commit -m "test: live Hardcover availability check (skipif no token)"
```

---

### Task G0.5: ⛔ Run the gate for real

**Files:** none (operational). **Precondition:** `.env` has a valid `HARDCOVER_API_TOKEN`; migrations applied (A9) so the `analysis_runs` write succeeds.

- [ ] **Step 1: Run the command against the live API**

Run: `uv run lacuna validate-hardcover`
Expected: `PASS — 'Atomic Habits': N live reviews` and exit code 0.

- [ ] **Step 2: Confirm the run was logged**

Run:
```bash
uv run python -c "import asyncio; from sqlalchemy import text; from lacuna.db.session import build_engine; e=build_engine(); print('see _verify script')"
```
(or add a one-off `scripts/_last_run.py` selecting `mode, status, counts from analysis_runs order by id desc limit 1`).
Expected: a `validation` row with `status='ok'` and `counts={'review_count': N}`.

- [ ] **Step 3: GATE DECISION**
  - **PASS** → record it; C, E, D, F, G, H, I, J are unblocked. Return to the master plan and request the next plans.
  - **FAIL** → STOP. Report the `error` and the recorded run. The "fresh sentiment" design needs revisiting before any scoring/fusion work (CLAUDE.md §2 — flag and confirm).

- [ ] **Step 4: Commit any operational scripts created**

```bash
git add -A
git commit -m "chore: G0 gate executed against live Hardcover API"
```

---

## Self-review (against PRD)

- **§18 gate semantics** — the gate is a real command with an exit code; the plan explicitly blocks F/G/H and includes a STOP/PASS decision step. ✓
- **§17.2** — fetches a real title and confirms live review availability; logged to `analysis_runs(mode='validation')`. ✓
- **§15 contract test** — live-availability check present, `skipif`-guarded to keep the default suite offline. ✓
- **Local boundary** — no LLM API touched; pure adapter + DB. ✓
- **Type consistency** — `validate_hardcover`, `ValidationResult`, `make_db_recorder`, `HardcoverClient.fetch_book_by_title`, `AnalysisRun` reused exactly as defined in A/B. ✓
- **Placeholder scan** — complete code in every step; the only deferred bits are clearly-marked operational verify snippets. ✓
- **CLI test** — both `_run_validation` patches use a plain `lambda: ValidationResult(...)` (sync, matches the real sync signature). ✓

**After PASS:** return to `2026-06-17-lacuna-master.md` and request the C/E → D → F/G → H → I → J plans.
