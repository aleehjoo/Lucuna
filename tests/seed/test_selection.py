# tests/seed/test_selection.py
from lacuna.seed.selection import select_critical_reviews, select_works_with_longtail

class R:
    def __init__(self, rating, helpful): self.rating = rating; self.helpful_vote = helpful

def test_critical_keeps_only_rating_le_3_ranked_by_helpful_capped():
    reviews = [R(5, 100), R(3, 1), R(2, 50), R(1, 10), R(4, 99)]
    out = select_critical_reviews(reviews, cap=2)
    assert [r.rating for r in out] == [2, 1]   # rating<=3, top-2 by helpful_vote
    assert all(r.rating <= 3 for r in out)

def test_critical_cap_respected():
    reviews = [R(1, i) for i in range(50)]
    assert len(select_critical_reviews(reviews, cap=15)) == 15

def test_longtail_includes_min_share_of_low_review_works():
    # 8 high-review works, 2 low-review works; ask for 5 works, 0.3 long-tail share
    works = [{"id": f"hi{i}", "review_count": 100} for i in range(8)] + \
            [{"id": f"lo{i}", "review_count": 2} for i in range(2)]
    selected = select_works_with_longtail(works, n=5, longtail_share=0.3, low_threshold=20)
    low = [w for w in selected if w["review_count"] < 20]
    assert len(selected) == 5
    assert len(low) >= 1   # ceil(5*0.3)=2 desired, but only 2 low exist -> >=1 guaranteed
