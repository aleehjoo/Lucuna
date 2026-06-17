# Workstream J — Docs & Final Verification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]`.

**Goal:** Complete documentation and the final acceptance verification against PRD §17. Docs and the source-scoped guard test ship without credentials; the live contract checks and the end-to-end acceptance run happen after the gate passes.

**Depends on:** all. 

## Already delivered (committed before the gate)
- `docs/METHODOLOGY.md` — scoring + aggregation math, all approved-default knobs.
- `docs/LIMITATIONS.md` — credibility doc (time-skew, survivorship, demand-as-proxy, legal mosaic).
- `README.md` — click-by-click Supabase + keys + `uv` setup.
- `tests/test_no_reddit.py` — guards source dirs against Reddit + Docker scaffolding (passing).
- Contract tests with recorded responses per source (Workstream B) + live Hardcover check (G0, skipif-guarded).
- `uv.lock` committed; HF dataset/model revisions resolved+verified+pinned (Workstream A).

---

### Task J1: Acceptance-criteria verification harness (`tests/test_acceptance_static.py`)

Static (no-credential) acceptance checks that can run now; the live ones are listed for the post-gate run.

**Files:** Create `tests/test_acceptance_static.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_acceptance_static.py
"""Static slices of PRD §17 acceptance criteria runnable without credentials."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_uv_lock_and_pins_present():  # §17.13, §17.4
    assert (ROOT / "uv.lock").exists()
    adv = (ROOT / "config" / "advanced.yaml").read_text(encoding="utf-8")
    assert "<resolved-at-build>" not in adv and "PINNED" not in adv
    # three 40-char-ish sha hex strings present
    import re
    assert len(re.findall(r"\b[0-9a-f]{40}\b", adv)) >= 3

def test_no_docker_compose_file():  # §17.1 (no Docker)
    assert not (ROOT / "docker-compose.yml").exists()
    assert not (ROOT / "Dockerfile").exists()

def test_env_example_has_no_reddit_key():  # §17.12
    assert "reddit" not in (ROOT / ".env.example").read_text(encoding="utf-8").lower()
```

- [ ] **Step 2: Run → pass.** `python -m uv run pytest tests/test_acceptance_static.py -v`
- [ ] **Step 3: Commit** `git commit -m "test(J): static acceptance checks (pins, no-docker, no-reddit)"`

---

### Task J2: Post-gate acceptance run (operational checklist — after credentials)

Run after `.env` is filled, `pgvector` enabled, and the G0 gate passes. Each maps to PRD §17:

- [ ] `uv run alembic upgrade head` provisions the full schema; verify 11 tables + pgvector (§17.1).
- [ ] `uv run lacuna validate-hardcover` passes the gate (§17.2) — **prerequisite for the rest**.
- [ ] `uv run lacuna seed` populates distilled tables via local NLP; confirm **zero** raw-corpus files committed (`git status` clean of `*.parquet`/`*.jsonl`) (§17.3).
- [ ] App runs end-to-end with `ANTHROPIC_API_KEY` unset; confirm no raw review text leaves the machine (§17.5).
- [ ] `uv run lacuna analyze --isbn <isbn>` returns clustered complaints + provenance + valid pack (JSON+MD) in ≤~2 min first run (§17.6).
- [ ] Fresh Hardcover data normalized per platform + fused; `cross_platform_agreement_pct` surfaced; agreement reflected in confidence (§17.7).
- [ ] Scoring never zeroes a missing layer (incomplete set / imputed); genuine zero propagates; blind_spot + recent_supply_surge behave (§17.8).
- [ ] Both modes run (single-title + sweep) (§17.9).
- [ ] Two projects coexist isolated via `project_id` (§17.10).
- [ ] Every dashboard panel shows provenance; freshness indicator dims; no dead ends (§17.11).
- [ ] `LACUNA_RUN_MODEL_SMOKE=1 uv run pytest tests/nlp/test_models_smoke.py` green (real MiniLM/bart load at pinned revision).
- [ ] Full suite + live Hardcover contract test green (§17.13).

- [ ] **Step (final):** `git commit -m "chore(J): post-gate acceptance run recorded"` (with any operational scripts/notes created).

---

## Self-review (against PRD §16/§17)

- README / METHODOLOGY / LIMITATIONS delivered ✓ · contract tests + live check present ✓ · uv.lock + pinned revisions ✓ · no-Reddit/no-Docker guards ✓ · static acceptance slice automated; live acceptance enumerated for the post-gate run ✓.
