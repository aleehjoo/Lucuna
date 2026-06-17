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
