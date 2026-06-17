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
