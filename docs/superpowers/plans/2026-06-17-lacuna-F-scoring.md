# Workstream F — Market-Gap Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]`.
>
> **⛔ GATE:** Per CLAUDE.md §4 / PRD §18, **do not author or run this code until `lacuna validate-hardcover` (G0) passes.** This plan is written and ready; execution is deferred to the post-gate phase.

**Goal:** Implement resilient market-gap scoring (PRD §10): rank normalization, missing≠zero handling, soft demand gate, weighted geometric mean, time-skew guard, and mandatory validity outputs — as **pure, cohort-level functions** that unit-test offline with hand-computed vectors.

**Architecture:** All math is pure and DB-free. `normalize.py` (rank norm, sigmoid, weighted geomean); `components.py` (build `(value, present)` triples — `present=False` ⇒ absent/never-zero, `present=True,value=0.0` ⇒ genuine zero); `validity.py` (confidence composite + flags); `gap_score.py` (`score_cohort()` orchestrator + pure `compose_gap()`). A thin DB layer (read distilled tables → Candidates, write `scores`) is the only integration piece, added when Supabase is live.

**Tech Stack:** numpy, scipy.stats.rankdata, stdlib math.

**Depends on:** D, E, G0. **Blocks:** H, I.

> **Design notes (Sequential Thinking):** scoring is **cohort-level** (imputation needs the cohort median; rank norm needs the population) — the entrypoint is `score_cohort(candidates)`, never `score_one()`. The absent-vs-genuine-zero distinction is carried as `Optional[float]` on each component (None = absent). Worked vector: demand_norm=0.5, supply_norm=0.8, unmet_norm=0.6 → gate=sigmoid(8·0.1)=0.6900, core=√0.48=0.6928, gap=**0.4780**.

---

### Task F1: Math primitives (`lacuna/scoring/normalize.py`)

**Files:** Create `lacuna/scoring/__init__.py` (empty), `lacuna/scoring/normalize.py`; Test `tests/scoring/__init__.py` (empty), `tests/scoring/test_normalize.py`

- [ ] **Step 1: Failing test**

```python
# tests/scoring/test_normalize.py
import math
from lacuna.scoring.normalize import rank_normalize, sigmoid, weighted_geomean

def test_rank_normalize_spreads_to_unit_interval():
    assert rank_normalize([10, 20, 30]) == [0.0, 0.5, 1.0]

def test_rank_normalize_is_outlier_robust():
    # one mega value must not compress the rest toward zero (ranks, not raw)
    out = rank_normalize([1, 2, 3, 1000])
    assert out == [0.0, 1/3, 2/3, 1.0]

def test_rank_normalize_single_is_neutral():
    assert rank_normalize([42]) == [0.5]
    assert rank_normalize([]) == []

def test_sigmoid_midpoint():
    assert abs(sigmoid(0) - 0.5) < 1e-9

def test_weighted_geomean_equal_weights():
    assert abs(weighted_geomean([0.8, 0.6], [1.0, 1.0]) - math.sqrt(0.48)) < 1e-9

def test_weighted_geomean_genuine_zero_propagates():
    assert weighted_geomean([0.0, 0.9], [1.0, 1.0]) == 0.0
```

- [ ] **Step 2: Run → fail.** `python -m uv run pytest tests/scoring/test_normalize.py -v`

- [ ] **Step 3: Implement**

```python
# lacuna/scoring/normalize.py
"""Pure scoring math (PRD §10)."""
from __future__ import annotations

import math

from scipy.stats import rankdata


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def rank_normalize(values: list[float]) -> list[float]:
    """Percentile-rank to [0,1]: (rank-1)/(n-1). n==1 → 0.5 (neutral). Outlier-robust."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [0.5]
    ranks = rankdata(values, method="average")  # 1..n, ties averaged
    return [(r - 1) / (n - 1) for r in ranks]


def weighted_geomean(values: list[float], weights: list[float]) -> float:
    """(∏ v_i^w_i)^(1/Σw). pow-form so a genuine 0 → 0 without log(0)."""
    total = sum(weights)
    prod = 1.0
    for v, w in zip(values, weights):
        prod *= max(0.0, min(1.0, v)) ** w
    return prod ** (1.0 / total)
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(F): scoring math primitives (rank norm, sigmoid, weighted geomean)"`

---

### Task F2: Components — absent vs genuine zero (`lacuna/scoring/components.py`)

**Files:** Create `lacuna/scoring/components.py`; Test `tests/scoring/test_components.py`

- [ ] **Step 1: Failing test**

```python
# tests/scoring/test_components.py
from lacuna.scoring.components import Candidate, derive_components

def test_present_zero_is_genuine_and_absent_is_none():
    c = derive_components(
        ref_id="w1", scope="work",
        demand_rows=[{"value": 5.0}],            # demand present
        title_count=0,                            # genuine zero supply -> scarcity present, max
        cluster_weights=[],                       # no clusters -> unmet absent
    )
    assert isinstance(c, Candidate)
    assert c.demand is not None
    assert c.supply_scarcity is not None          # title_count present (even 0)
    assert c.unmet_need is None                    # absent (no clusters), NOT zero

def test_unmet_need_is_sum_of_reviewer_times_helpful():
    c = derive_components(ref_id="w", scope="work", demand_rows=[{"value": 1}],
                          title_count=10,
                          cluster_weights=[(3, 2.0), (1, 1.0)])  # (reviewer_count, helpful_weight)
    assert c.unmet_need == 3 * 2.0 + 1 * 1.0

def test_demand_absent_when_no_rows():
    c = derive_components(ref_id="w", scope="work", demand_rows=[],
                          title_count=10, cluster_weights=[(1, 1.0)])
    assert c.demand is None
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement**

```python
# lacuna/scoring/components.py
"""Derive the three raw scoring components from distilled data (PRD §9/§10).
None means ABSENT (never treated as zero); a real 0.0 propagates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Candidate:
    ref_id: str
    scope: str  # 'work' | 'bisac'
    demand: float | None
    supply_scarcity: float | None
    unmet_need: float | None
    sample_size: int = 0
    platforms: tuple[str, ...] = ()
    oldest_signal: date | None = None
    newest_signal: date | None = None
    crosswalk_conf: float = 1.0
    recent_share: float = 0.0  # recent_title_count / title_count


def derive_components(
    *, ref_id: str, scope: str,
    demand_rows: list[dict],
    title_count: int | None,
    cluster_weights: list[tuple[int, float]],
    sample_size: int = 0,
    platforms: tuple[str, ...] = (),
    oldest_signal: date | None = None,
    newest_signal: date | None = None,
    crosswalk_conf: float = 1.0,
    recent_share: float = 0.0,
) -> Candidate:
    # demand: present iff >=1 demand_signal row; sum of available metric values
    demand = sum(float(r["value"]) for r in demand_rows) if demand_rows else None
    # supply_scarcity: inverse of supply. present iff title_count is not None (0 is genuine).
    supply_scarcity = (float(-title_count)) if title_count is not None else None
    # unmet_need: sum(reviewer_count * helpful_weight); absent iff no clusters
    unmet_need = sum(rc * hw for rc, hw in cluster_weights) if cluster_weights else None
    return Candidate(
        ref_id=ref_id, scope=scope, demand=demand,
        supply_scarcity=supply_scarcity, unmet_need=unmet_need,
        sample_size=sample_size, platforms=tuple(platforms),
        oldest_signal=oldest_signal, newest_signal=newest_signal,
        crosswalk_conf=crosswalk_conf, recent_share=recent_share,
    )
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(F): component derivation with absent-vs-genuine-zero semantics"`

---

### Task F3: Validity & confidence (`lacuna/scoring/validity.py`)

**Files:** Create `lacuna/scoring/validity.py`; Test `tests/scoring/test_validity.py`

- [ ] **Step 1: Failing test**

```python
# tests/scoring/test_validity.py
from lacuna.scoring.validity import compute_confidence, clamp01

def test_clamp():
    assert clamp01(-0.2) == 0.0 and clamp01(1.5) == 1.0 and clamp01(0.4) == 0.4

def test_confidence_full_data_two_platforms():
    # sample 40 >= gate 20 -> 1.0; no imputation; two platforms; crosswalk 1.0
    c = compute_confidence(sample_size=40, min_sample_gate=20, imputed_layers=0,
                           single_platform=False, crosswalk_conf=1.0)
    assert abs(c - 1.0) < 1e-9

def test_confidence_penalised_for_small_sample_imputation_singleplatform():
    # sample 10/20=0.5 ; one imputed *0.7 ; single platform *0.85 ; crosswalk 0.9
    c = compute_confidence(sample_size=10, min_sample_gate=20, imputed_layers=1,
                           single_platform=True, crosswalk_conf=0.9)
    assert abs(c - (0.5 * 0.7 * 0.85 * 0.9)) < 1e-9
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement**

```python
# lacuna/scoring/validity.py
"""Confidence composite + clamp (PRD §10; approved formula in METHODOLOGY.md)."""
from __future__ import annotations


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_confidence(*, sample_size: int, min_sample_gate: int, imputed_layers: int,
                       single_platform: bool, crosswalk_conf: float) -> float:
    sample_factor = min(1.0, sample_size / min_sample_gate) if min_sample_gate else 1.0
    imputation_factor = 0.7 ** imputed_layers
    platform_factor = 0.85 if single_platform else 1.0
    return clamp01(sample_factor * imputation_factor * platform_factor * crosswalk_conf)
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(F): confidence composite + clamp"`

---

### Task F4: Cohort scoring orchestrator (`lacuna/scoring/gap_score.py`)

**Files:** Create `lacuna/scoring/gap_score.py`; Test `tests/scoring/test_gap_score.py`

- [ ] **Step 1: Failing test** (hand-computed vectors)

```python
# tests/scoring/test_gap_score.py
import math
from lacuna.scoring.components import Candidate
from lacuna.scoring.gap_score import compose_gap, score_cohort, DEFAULT_CFG

def test_compose_gap_known_vector():
    # demand_norm=0.5, supply_norm=0.8, unmet_norm=0.6 -> gap≈0.4780
    gap = compose_gap(0.5, 0.8, 0.6, DEFAULT_CFG)
    assert abs(gap - (math.sqrt(0.48) * (1/(1+math.exp(-0.8))))) < 1e-9

def test_demand_absent_is_withheld_not_zero():
    cands = [Candidate("w1", "work", demand=None, supply_scarcity=-5.0, unmet_need=3.0, sample_size=30)]
    res = score_cohort(cands, DEFAULT_CFG)[0]
    assert res.gap_score is None and res.incomplete is True

def test_missing_supply_is_imputed_not_zeroed():
    cands = [
        Candidate("a", "work", demand=10, supply_scarcity=-2.0, unmet_need=5.0, sample_size=30),
        Candidate("b", "work", demand=20, supply_scarcity=None, unmet_need=4.0, sample_size=30),  # impute
        Candidate("c", "work", demand=30, supply_scarcity=-8.0, unmet_need=6.0, sample_size=30),
    ]
    res = {r.ref_id: r for r in score_cohort(cands, DEFAULT_CFG)}
    assert res["b"].gap_score is not None        # imputed, not zeroed
    assert res["b"].incomplete is True

def test_blind_spot_set_for_thin_sample():
    cands = [Candidate("t", "work", demand=10, supply_scarcity=-3.0, unmet_need=2.0, sample_size=5)]
    assert score_cohort(cands, DEFAULT_CFG)[0].blind_spot is True

def test_recent_supply_surge_downweights():
    base = Candidate("x", "work", demand=10, supply_scarcity=-3.0, unmet_need=4.0, sample_size=30)
    surge = Candidate("y", "work", demand=10, supply_scarcity=-3.0, unmet_need=4.0, sample_size=30, recent_share=0.5)
    out = {r.ref_id: r for r in score_cohort([base, surge], DEFAULT_CFG)}
    assert out["y"].recent_supply_surge is True
    assert out["y"].gap_score <= out["x"].gap_score
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement**

```python
# lacuna/scoring/gap_score.py
"""Cohort-level resilient gap scoring (PRD §10). Pure; DB I/O lives in the pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median

from lacuna.scoring.components import Candidate
from lacuna.scoring.normalize import rank_normalize, sigmoid, weighted_geomean
from lacuna.scoring.validity import clamp01, compute_confidence

DEFAULT_CFG = {
    "demand_gate_floor_epsilon": 0.05,
    "demand_gate_steepness_k": 8,
    "demand_gate_midpoint_d0": 0.4,
    "geomean_weight_supply": 1.0,
    "geomean_weight_unmet": 1.0,
    "min_sample_gate": 20,
    "recent_supply_surge_threshold": 0.30,
    "recent_supply_surge_downweight": 0.7,
}


@dataclass
class ScoreResult:
    ref_id: str
    scope: str
    demand_score: float | None
    supply_scarcity: float | None
    unmet_need: float | None
    gap_score: float | None
    confidence: float
    sample_size: int
    platforms_used: list[str]
    oldest_signal: date | None
    newest_signal: date | None
    incomplete: bool
    blind_spot: bool
    recent_supply_surge: bool


def compose_gap(demand_norm: float, supply_norm: float, unmet_norm: float, cfg: dict) -> float:
    gate = max(cfg["demand_gate_floor_epsilon"],
               sigmoid(cfg["demand_gate_steepness_k"] * (demand_norm - cfg["demand_gate_midpoint_d0"])))
    core = weighted_geomean([supply_norm, unmet_norm],
                            [cfg["geomean_weight_supply"], cfg["geomean_weight_unmet"]])
    return core * gate


def _normalize_with_imputation(raw: list[float | None]) -> tuple[list[float], list[bool]]:
    """Rank-normalize present values to [0,1]; impute missing as the median of the
    present normalized values. Returns (norms, imputed_flags)."""
    present_idx = [i for i, v in enumerate(raw) if v is not None]
    present_norms = rank_normalize([raw[i] for i in present_idx])
    norm_map = dict(zip(present_idx, present_norms))
    fill = median(present_norms) if present_norms else 0.5
    norms, imputed = [], []
    for i in range(len(raw)):
        if i in norm_map:
            norms.append(norm_map[i]); imputed.append(False)
        else:
            norms.append(fill); imputed.append(True)
    return norms, imputed


def score_cohort(candidates: list[Candidate], cfg: dict = DEFAULT_CFG) -> list[ScoreResult]:
    # Demand: candidates missing demand are WITHHELD; rank-normalize the rest together.
    demand_present = [c.demand is not None for c in candidates]
    demand_norm_map: dict[int, float] = {}
    present_idx = [i for i, p in enumerate(demand_present) if p]
    for i, dn in zip(present_idx, rank_normalize([candidates[i].demand for i in present_idx])):
        demand_norm_map[i] = dn

    supply_norms, supply_imp = _normalize_with_imputation([c.supply_scarcity for c in candidates])
    unmet_norms, unmet_imp = _normalize_with_imputation([c.unmet_need for c in candidates])

    results: list[ScoreResult] = []
    for i, c in enumerate(candidates):
        surge = c.recent_share > cfg["recent_supply_surge_threshold"]
        blind = c.sample_size < cfg["min_sample_gate"]
        imputed_layers = int(supply_imp[i]) + int(unmet_imp[i])

        if not demand_present[i]:
            results.append(ScoreResult(
                c.ref_id, c.scope, None, supply_norms[i], unmet_norms[i], None,
                confidence=compute_confidence(sample_size=c.sample_size,
                    min_sample_gate=cfg["min_sample_gate"], imputed_layers=imputed_layers + 1,
                    single_platform=len(c.platforms) <= 1, crosswalk_conf=c.crosswalk_conf),
                sample_size=c.sample_size, platforms_used=list(c.platforms),
                oldest_signal=c.oldest_signal, newest_signal=c.newest_signal,
                incomplete=True, blind_spot=blind, recent_supply_surge=surge))
            continue

        gap = compose_gap(demand_norm_map[i], supply_norms[i], unmet_norms[i], cfg)
        if surge:
            gap *= cfg["recent_supply_surge_downweight"]
        results.append(ScoreResult(
            c.ref_id, c.scope, demand_norm_map[i], supply_norms[i], unmet_norms[i], clamp01(gap),
            confidence=compute_confidence(sample_size=c.sample_size,
                min_sample_gate=cfg["min_sample_gate"], imputed_layers=imputed_layers,
                single_platform=len(c.platforms) <= 1, crosswalk_conf=c.crosswalk_conf),
            sample_size=c.sample_size, platforms_used=list(c.platforms),
            oldest_signal=c.oldest_signal, newest_signal=c.newest_signal,
            incomplete=imputed_layers > 0, blind_spot=blind, recent_supply_surge=surge))
    return results


def load_cfg() -> dict:  # pragma: no cover
    """Merge advanced.yaml knobs over DEFAULT_CFG (used by the pipeline)."""
    from lacuna.config import load_advanced
    adv = load_advanced()
    return {**DEFAULT_CFG, **{k: adv[k] for k in DEFAULT_CFG if k in adv}}
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(F): resilient cohort gap scoring (missing≠zero, soft gate, geomean, time-skew)"`

---

### Task F5: DB read/write wrapper (integration — deferred until Supabase live)

**Files:** Create `lacuna/scoring/persist.py` (skeleton)

- [ ] **Step 1: Implement skeleton (no test now; integration-tested post-credentials)**

```python
# lacuna/scoring/persist.py
"""Read distilled tables -> Candidates; write ScoreResults -> scores. Integration
layer (needs Supabase). Pure scoring is in gap_score.py and fully unit-tested."""
from __future__ import annotations

from lacuna.scoring.components import Candidate
from lacuna.scoring.gap_score import ScoreResult


async def load_candidates(project_id: str, scope: str) -> list[Candidate]:  # pragma: no cover
    raise NotImplementedError("requires Supabase; see gap_score.score_cohort for the pure logic")


async def write_scores(project_id: str, results: list[ScoreResult]) -> None:  # pragma: no cover
    raise NotImplementedError("requires Supabase; upserts into scores (unique project_id,scope,ref_id)")
```

- [ ] **Step 2: Commit** `git commit -m "feat(F): scoring persistence skeleton (integration deferred)"`

---

## Self-review (against PRD §10)

- Rank/percentile normalization (outlier-robust, n=1 neutral) ✓ · missing≠zero (withhold demand / impute supply·unmet median + confidence penalty) ✓ · genuine zero propagates (geomean pow-form) ✓ · soft epsilon-floored demand gate ✓ · weighted geometric mean core ✓ · compose ✓ · time-skew guard (surge flag + downweight) ✓ · all validity outputs (confidence/sample_size/platforms/dates/incomplete/blind_spot/recent_supply_surge) ✓.
- Cohort-level entrypoint (imputation+rank need the population) ✓. Pure & offline-testable with hand-computed vectors ✓. DB I/O isolated in `persist.py` (deferred) ✓.
