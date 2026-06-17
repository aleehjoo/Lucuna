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
