# Workstream H — LLM Context Pack Export — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]`.
>
> **⛔ GATE:** Per CLAUDE.md §4 / PRD §18, **do not author or run this code until G0 passes.** Ready, deferred.

**Goal:** Emit the LLM-ready Context Pack as a **JSON + Markdown twin** (PRD §12) built from paraphrased aspect clusters (never raw review text), honoring `max_candidates` and `token_budget`. Optional `ANTHROPIC_API_KEY` adds a local narrative; the pack is complete without it (runs at $0).

**Architecture:** Pure builders — `build_pack(...)` → dict matching the §12 schema; `to_markdown(pack, token_budget)` → compact string with the hypothesis banner, legend, limitations, bulleted candidates, truncated to budget. The optional Anthropic call is isolated in `narrative.py` and only ever receives the **already-aggregated pack** (never raw reviews), gated behind the key.

**Tech Stack:** stdlib json; (optional) anthropic SDK. No raw review text anywhere.

**Depends on:** F, G, G0. **Blocks:** I.

> **Design note:** the only external-LLM touchpoint in the whole system lives here and sees aggregated clusters only (PRD §7) — preserving the zero-raw-text boundary.

---

### Task H1: Pack builder (`lacuna/export/context_pack.py`)

**Files:** Create `lacuna/export/__init__.py` (empty), `lacuna/export/context_pack.py`; Test `tests/export/__init__.py` (empty), `tests/export/test_context_pack.py`

- [ ] **Step 1: Failing test**

```python
# tests/export/test_context_pack.py
from lacuna.export.context_pack import build_pack, Candidate, Complaint

def _cand(ref="w1", gap=0.48, n=30):
    return Candidate(
        ref="work", title_or_subject=ref, gap_score=gap,
        demand=0.5, supply_scarcity=0.8, unmet_need=0.6,
        confidence=0.9, sample_size=n, platforms=["amazon_corpus", "hardcover"],
        oldest_signal="2019-01-01", newest_signal="2026-06-01",
        incomplete=False, blind_spot=False, recent_supply_surge=False,
        top_complaints=[Complaint("outdated examples", 10, 5.0, ["amazon_corpus", "hardcover"], True)],
        demand_evidence={"nyt_weeks": 12, "ratings_count": 500, "read_count": 0, "review_velocity_per_mo": 3.0},
    )

def test_pack_has_required_top_level_keys():
    pack = build_pack(project="P", bisac=["SEL036000"], mode="single_title",
                      generated_at="2026-06-17T00:00:00Z",
                      platforms_used=["amazon_corpus", "hardcover"],
                      total_reviews=120, cross_platform_agreement_pct=0.67,
                      candidates=[_cand()], max_candidates=15)
    for k in ("legend", "instructions_to_model", "known_limitations", "target",
              "generated_at", "provenance", "candidates"):
        assert k in pack
    assert pack["target"]["mode"] == "single_title"
    assert pack["provenance"]["cross_platform_agreement_pct"] == 0.67
    assert pack["candidates"][0]["validity"]["confidence"] == 0.9
    # paraphrased complaint, never a raw quote field
    assert "text" not in pack["candidates"][0]["top_complaints"][0]

def test_max_candidates_truncates():
    pack = build_pack(project="P", bisac=["X"], mode="category_sweep",
                      generated_at="t", platforms_used=["amazon_corpus"], total_reviews=1,
                      cross_platform_agreement_pct=0.0,
                      candidates=[_cand(f"w{i}", gap=1 - i*0.1) for i in range(20)],
                      max_candidates=5)
    assert len(pack["candidates"]) == 5
    # sorted by gap_score desc
    gaps = [c["gap_score"] for c in pack["candidates"]]
    assert gaps == sorted(gaps, reverse=True)
```

- [ ] **Step 2: Run → fail.** `python -m uv run pytest tests/export/test_context_pack.py -v`

- [ ] **Step 3: Implement**

```python
# lacuna/export/context_pack.py
"""LLM Context Pack (PRD §12). JSON + Markdown twin from paraphrased clusters only."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

LEGEND = ("gap_score 0-1, higher=more underserved. unmet_need is demand-gated (soft). "
          "Every score carries confidence + provenance.")
INSTRUCTIONS = [
    "Treat each candidate as a HYPOTHESIS, not a finding.",
    "Do NOT infer demand from dissatisfaction alone; demand must come from the demand fields.",
    "For each candidate state: strongest case FOR, strongest case AGAINST, and what live Amazon data would confirm or kill it.",
    "Down-weight candidates with confidence < 0.5, incomplete=true, recent_supply_surge=true, or newest_signal older than 18 months.",
    "Name what is NOT in this data: post-2023 trends, true greenfield gaps, actual unit sales.",
]
LIMITATIONS = [
    "Deep sentiment corpus ends 2023-09; US amazon.com / English only.",
    "Fresh layer (Hardcover) has thinner volume than Amazon; some titles carry little signal.",
    "Demand is a popularity PROXY, not unit sales or BSR.",
    "Survivorship: unwritten books leave no trace — thin data may be a blind spot, not an opportunity.",
    "Ratings are dissatisfaction signals, not willingness-to-pay.",
]


@dataclass
class Complaint:
    aspect: str
    reviewer_count: int
    helpful_weight: float
    platforms: list[str]
    cross_platform: bool


@dataclass
class Candidate:
    ref: str
    title_or_subject: str
    gap_score: float
    demand: float
    supply_scarcity: float
    unmet_need: float
    confidence: float
    sample_size: int
    platforms: list[str]
    oldest_signal: str | None
    newest_signal: str | None
    incomplete: bool
    blind_spot: bool
    recent_supply_surge: bool
    top_complaints: list[Complaint] = field(default_factory=list)
    demand_evidence: dict = field(default_factory=dict)


def _candidate_json(c: Candidate) -> dict:
    return {
        "ref": c.ref,
        "title_or_subject": c.title_or_subject,
        "gap_score": c.gap_score,
        "components": {"demand": c.demand, "supply_scarcity": c.supply_scarcity, "unmet_need": c.unmet_need},
        "validity": {
            "confidence": c.confidence, "sample_size": c.sample_size, "platforms": c.platforms,
            "oldest_signal": c.oldest_signal, "newest_signal": c.newest_signal,
            "incomplete": c.incomplete, "blind_spot": c.blind_spot, "recent_supply_surge": c.recent_supply_surge,
        },
        "top_complaints": [asdict(t) for t in c.top_complaints],
        "demand_evidence": c.demand_evidence,
    }


def build_pack(*, project: str, bisac: list[str], mode: str, generated_at: str,
               platforms_used: list[str], total_reviews: int,
               cross_platform_agreement_pct: float, candidates: list[Candidate],
               max_candidates: int) -> dict:
    ranked = sorted(candidates, key=lambda c: c.gap_score, reverse=True)[:max_candidates]
    return {
        "legend": LEGEND,
        "instructions_to_model": INSTRUCTIONS,
        "known_limitations": LIMITATIONS,
        "target": {"project": project, "bisac": bisac, "mode": mode},
        "generated_at": generated_at,
        "provenance": {
            "platforms_used": platforms_used,
            "total_reviews": total_reviews,
            "cross_platform_agreement_pct": cross_platform_agreement_pct,
        },
        "candidates": [_candidate_json(c) for c in ranked],
    }
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(H): Context Pack JSON builder (paraphrased clusters, ranked, capped)"`

---

### Task H2: Markdown twin with token budget (`context_pack.py` cont.)

**Files:** Modify `lacuna/export/context_pack.py`; Test `tests/export/test_markdown.py`

- [ ] **Step 1: Failing test**

```python
# tests/export/test_markdown.py
from lacuna.export.context_pack import build_pack, to_markdown, Candidate, Complaint

def _pack(nc=10):
    cands = [Candidate(ref="work", title_or_subject=f"Title {i}", gap_score=1 - i*0.05,
                       demand=0.5, supply_scarcity=0.5, unmet_need=0.5, confidence=0.8,
                       sample_size=30, platforms=["amazon_corpus"], oldest_signal="2019-01-01",
                       newest_signal="2026-01-01", incomplete=False, blind_spot=False,
                       recent_supply_surge=False,
                       top_complaints=[Complaint("outdated", 5, 2.0, ["amazon_corpus"], False)],
                       demand_evidence={"nyt_weeks": 1, "ratings_count": 10, "read_count": 0, "review_velocity_per_mo": 0.0})
             for i in range(nc)]
    return build_pack(project="P", bisac=["X"], mode="single_title", generated_at="t",
                      platforms_used=["amazon_corpus"], total_reviews=1,
                      cross_platform_agreement_pct=0.0, candidates=cands, max_candidates=nc)

def test_markdown_has_banner_and_legend():
    md = to_markdown(_pack(3), token_budget=4000)
    assert "Treat as hypotheses" in md
    assert "gap_score" in md

def test_token_budget_truncates_candidates():
    full = to_markdown(_pack(10), token_budget=4000)
    tiny = to_markdown(_pack(10), token_budget=200)
    assert len(tiny) < len(full)
    # budget honored (~4 chars/token heuristic)
    assert len(tiny) <= 200 * 5
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Append to `context_pack.py`**

```python
def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)  # ~4 chars/token heuristic


def to_markdown(pack: dict, *, token_budget: int = 4000) -> str:
    head = [
        f"# Lacuna Context Pack — {pack['target']['project']}",
        "> Treat as hypotheses, not findings.",
        f"_Legend:_ {pack['legend']}",
        f"_Mode:_ {pack['target']['mode']} · _BISAC:_ {', '.join(pack['target']['bisac'])} · "
        f"_Agreement:_ {pack['provenance']['cross_platform_agreement_pct']:.0%}",
        "## Known limitations",
        *[f"- {l}" for l in pack["known_limitations"]],
        "## Candidates",
    ]
    out = list(head)
    for c in pack["candidates"]:
        v = c["validity"]
        block = [
            f"### {c['title_or_subject']} — gap {c['gap_score']:.2f} "
            f"(conf {v['confidence']:.2f}, n={v['sample_size']}, {', '.join(v['platforms'])})",
            *([f"  - flags: "
               + ", ".join(f for f, on in (("incomplete", v["incomplete"]),
                                           ("blind_spot", v["blind_spot"]),
                                           ("recent_supply_surge", v["recent_supply_surge"])) if on)]
              if (v["incomplete"] or v["blind_spot"] or v["recent_supply_surge"]) else []),
            *[f"  - {t['aspect']} (reviewers {t['reviewer_count']}, "
              f"{'cross-platform' if t['cross_platform'] else t['platforms'][0]})"
              for t in c["top_complaints"]],
        ]
        candidate_text = "\n".join(block)
        if _approx_tokens("\n".join(out) + "\n" + candidate_text) > token_budget:
            out.append("_(truncated to honor token_budget)_")
            break
        out.append(candidate_text)
    return "\n".join(out)
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(H): Markdown twin with hypothesis banner + token budget"`

---

### Task H3: Optional local narrative (`lacuna/export/narrative.py`)

**Files:** Create `lacuna/export/narrative.py`; Test `tests/export/test_narrative.py`

> The pack must be complete with `ANTHROPIC_API_KEY` unset (PRD §17.5). The Anthropic call (if any) sees the aggregated pack only — never raw reviews.

- [ ] **Step 1: Failing test**

```python
# tests/export/test_narrative.py
from lacuna.export.narrative import maybe_add_narrative

def test_no_key_returns_pack_unchanged():
    pack = {"candidates": []}
    out = maybe_add_narrative(pack, api_key=None)
    assert out is pack and "narrative" not in out

def test_with_key_uses_injected_client_and_sees_only_pack(monkeypatch):
    seen = {}
    def fake_caller(api_key, pack):
        seen["pack"] = pack
        return "Summary: two strong hypotheses."
    pack = {"candidates": [{"title_or_subject": "X"}]}
    out = maybe_add_narrative(pack, api_key="sk-test", _caller=fake_caller)
    assert out["narrative"].startswith("Summary")
    assert seen["pack"] is pack  # only the aggregated pack passed, no raw reviews
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement**

```python
# lacuna/export/narrative.py
"""Optional Anthropic narrative (PRD §12). Disabled when no key; only ever sees the
already-aggregated pack (never raw review text)."""
from __future__ import annotations

from collections.abc import Callable


def _default_caller(api_key: str, pack: dict) -> str:  # pragma: no cover
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-opus-4-8", max_tokens=600,
        messages=[{"role": "user", "content":
                   "These are aggregated, anonymized market-gap candidates (no raw reviews). "
                   "Write a brief, skeptical analyst summary treating each as a hypothesis:\n"
                   + str(pack["candidates"])}],
    )
    return msg.content[0].text


def maybe_add_narrative(pack: dict, *, api_key: str | None,
                        _caller: Callable[[str, dict], str] = _default_caller) -> dict:
    if not api_key:
        return pack
    pack["narrative"] = _caller(api_key, pack)
    return pack
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(H): optional Anthropic narrative (off by default, aggregated-only)"`

---

## Self-review (against PRD §12)

- JSON + Markdown twin ✓ · paraphrased clusters only, no raw `text` field (test asserts) ✓ · legend + instructions_to_model + known_limitations + provenance + validity per candidate ✓ · `max_candidates` + `token_budget` honored ✓ · hypothesis banner ✓ · optional narrative, complete without key, aggregated-only (boundary preserved) ✓ · pure & offline-testable ✓.
