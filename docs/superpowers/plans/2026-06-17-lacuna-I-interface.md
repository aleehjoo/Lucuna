# Workstream I — Interface (CLI + Dashboard) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]`.
>
> **⛔ GATE:** Depends on F, G, H (which are G0-gated). The **pure helpers + CLI wiring** below are offline-testable; the pipeline orchestrators and Streamlit app are integration (need Supabase + a passed gate) and are exercised after credentials.

**Goal:** Ship both modes end-to-end (PRD §11/§14): a Typer CLI (`seed`, `analyze`, `sweep`, `export`) and a Streamlit dashboard with provenance on every panel, a timely↔evergreen slider whose freshness indicator **dims** toward "timely", and no dead ends.

**Architecture:** `pipeline/single_title.py` + `pipeline/category_sweep.py` orchestrate adapters→NLP(D)→aggregation(G)→scoring(F)→export(H) over Supabase (integration). The CLI extends the existing `app/cli.py` (the `@app.callback()` from G0 keeps it a group). `app/streamlit_app.py` reads distilled tables for responsiveness. A pure `freshness.py` helper computes the dimming indicator and is unit-tested now.

**Depends on:** F, G, H. **Blocks:** J (final pass).

---

### Task I1: Freshness-dimming helper (pure, offline) (`lacuna/pipeline/freshness.py`)

**Files:** Create `lacuna/pipeline/freshness.py`; Test `tests/pipeline/__init__.py` (empty), `tests/pipeline/test_freshness.py`

- [ ] **Step 1: Failing test**

```python
# tests/pipeline/test_freshness.py
import math
from lacuna.pipeline.freshness import freshness_opacity

def test_evergreen_is_full_opacity():
    # slider 0 = evergreen depth -> indicator fully lit (fresh layer not emphasized)
    assert math.isclose(freshness_opacity(0.0), 1.0)

def test_timely_dims_indicator():
    # slider 1 = timely -> indicator dimmed (honest signal the fresh layer is thinner)
    assert math.isclose(freshness_opacity(1.0), 0.3)   # float-safe (1.0-0.7 != 0.3 exactly)
    assert 0.3 < freshness_opacity(0.5) < 1.0

def test_clamped():
    assert math.isclose(freshness_opacity(-1), 1.0)
    assert math.isclose(freshness_opacity(2), 0.3)
```

- [ ] **Step 2: Run → fail.** `python -m uv run pytest tests/pipeline/test_freshness.py -v`

- [ ] **Step 3: Implement**

```python
# lacuna/pipeline/freshness.py
"""Pure helper for the timely<->evergreen freshness indicator (PRD §14).
Dims toward 'timely' to honestly signal the fresh layer is thinner."""
from __future__ import annotations

MIN_OPACITY = 0.3
MAX_OPACITY = 1.0


def freshness_opacity(slider: float) -> float:
    """slider in [0,1]: 0=evergreen (full opacity), 1=timely (dimmed)."""
    s = max(0.0, min(1.0, slider))
    return MAX_OPACITY - s * (MAX_OPACITY - MIN_OPACITY)
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(I): pure freshness-dimming helper for the slider"`

---

### Task I2: CLI commands wired (registration testable offline) (`app/cli.py`)

**Files:** Modify `app/cli.py`; Test `tests/test_cli_commands.py`

- [ ] **Step 1: Failing test** (asserts the commands exist; execution is integration)

```python
# tests/test_cli_commands.py
import typer
import app.cli as cli

def test_all_commands_registered():
    group = typer.main.get_command(cli.app)
    names = set(group.commands.keys())
    assert {"validate-hardcover", "seed", "analyze", "sweep", "export"}.issubset(names)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Add commands to `app/cli.py`** (append; each calls a pipeline entrypoint that raises until integration is wired)

```python
# --- appended to app/cli.py ---
@app.command("seed")
def seed_cmd(rebuild: bool = typer.Option(False), reconcile: bool = typer.Option(False)) -> None:
    """Run the offline seed for the configured project."""
    from lacuna.seed.seed import run_seed
    run_seed(rebuild=rebuild, reconcile=reconcile)


@app.command("analyze")
def analyze_cmd(isbn: str = typer.Option(None), title: str = typer.Option(None),
                out: str = typer.Option("pack.json")) -> None:
    """Single-Title Watchlist analysis -> summary + Context Pack."""
    from lacuna.pipeline.single_title import analyze
    import asyncio
    asyncio.run(analyze(isbn=isbn, title=title, out=out))


@app.command("sweep")
def sweep_cmd(out: str = typer.Option("sweep_pack.json")) -> None:
    """Category Sweep for the configured project (advanced, lower-confidence)."""
    from lacuna.pipeline.category_sweep import sweep
    import asyncio
    asyncio.run(sweep(out=out))


@app.command("export")
def export_cmd(out: str = typer.Option("pack.json")) -> None:
    """(Re)generate the Context Pack from the latest scores."""
    from lacuna.pipeline.single_title import export_only
    import asyncio
    asyncio.run(export_only(out=out))
```

- [ ] **Step 4: Run → pass** (registration). Execution of seed/analyze/sweep raises NotImplementedError until I3 integration.

- [ ] **Step 5: Commit** `git commit -m "feat(I): register seed/analyze/sweep/export CLI commands"`

---

### Task I3: Pipeline orchestrators (integration — deferred until Supabase + gate)

**Files:** Create `lacuna/pipeline/single_title.py`, `lacuna/pipeline/category_sweep.py` (skeletons)

```python
# lacuna/pipeline/single_title.py
"""Single-Title Watchlist pipeline (PRD §11): resolve work -> fresh pull (Hardcover/
Google Books) -> merge with corpus clusters (G) -> score (F) -> export (H).
Integration; needs Supabase + pinned models + passed G0 gate."""
from __future__ import annotations


async def analyze(*, isbn: str | None, title: str | None, out: str) -> None:  # pragma: no cover
    raise NotImplementedError("single_title.analyze: wire after G0 passes + Supabase live")


async def export_only(*, out: str) -> None:  # pragma: no cover
    raise NotImplementedError("export_only: wire after scores exist")
```

```python
# lacuna/pipeline/category_sweep.py
"""Category Sweep pipeline (PRD §11): iterate works -> fuse at BISAC-bucket level ->
score per BISAC. Bounded by Hardcover 60/min. Integration; deferred."""
from __future__ import annotations


async def sweep(*, out: str) -> None:  # pragma: no cover
    raise NotImplementedError("category_sweep.sweep: wire after G0 passes + Supabase live")
```

- [ ] **Commit** `git commit -m "feat(I): single-title + category-sweep pipeline skeletons (deferred)"`

---

### Task I4: Streamlit dashboard (integration — deferred)

**Files:** Create `app/streamlit_app.py`

> Built against live distilled tables; not unit-tested (UI). Must implement (PRD §14): project switcher; Single-Title view (clustered complaints with reviewer_count/helpful_weight/platform badges/cross-platform flag, rating distribution, demand evidence, **provenance line on every panel**); Category Sweep view (ranked candidates with confidence/blind_spot/recent_supply_surge inline + advanced banner); timely↔evergreen slider using `freshness_opacity()` to dim the freshness indicator; empty/loading/error states; Context Pack download (JSON+MD). Wire every control to live queries.

- [ ] **Step 1: Implement `app/streamlit_app.py`** using `st.cache_data` for distilled-table reads, `st.selectbox` for the project switcher, `st.tabs` for the two modes, `st.slider` + `freshness_opacity()` for the dimming indicator, `st.download_button` for the pack. (Full implementation authored at execution time against the live schema; structure per PRD §14.)

- [ ] **Step 2: Manual smoke** (post-credentials): `uv run streamlit run app/streamlit_app.py` — verify both views render, provenance lines present, slider dims, downloads work, no dead ends.

- [ ] **Step 3: Commit** `git commit -m "feat(I): Streamlit dashboard (both modes, provenance, dimming slider)"`

---

## Self-review (against PRD §11/§14)

- Both modes shipped (single-title + sweep) ✓ · CLI seed/analyze/sweep/export registered ✓ · freshness dimming is a pure tested helper ✓ · provenance on every panel + advanced banner + empty/error states (dashboard spec) ✓ · pipelines orchestrate D→G→F→H ✓.
- **Offline now:** I1 (freshness), I2 (CLI registration). **Deferred:** I3/I4 integration (need Supabase + passed gate).
