# tests/seed/test_orchestrator.py
"""Offline test of the seed plan builder: fakes for the embedder/labeler so no
models, network, or DB are touched (PRD §7 boundary respected by construction)."""
import numpy as np

from lacuna.nlp.aspects import AspectResult
from lacuna.seed.orchestrator import build_seed_plan


class FakeRv:
    def __init__(self, parent_asin, rating, text, helpful=0, user="u", ts=None):
        self.parent_asin = parent_asin
        self.asin = parent_asin
        self.rating = rating
        self.text = text
        self.helpful_vote = helpful
        self.user_id = user
        self.timestamp = ts
        self.review_date = None


class FakeEmbedder:
    def encode(self, texts):
        return np.array([[float(len(t)), float(t.count(" ")), 1.0, 0.0] for t in texts])


class FakeLabeler:
    def label_cluster(self, texts, candidate_labels=None):
        return AspectResult(label="outdated", score=0.9,
                            representative="Readers say the material feels outdated.")


META = [
    {"parent_asin": "P1", "title": "Meditations", "author": {"name": "Marcus Aurelius"},
     "categories": ["Books", "Philosophy"], "details": {"format": "Paperback"}, "price": "12.99"},
    {"parent_asin": "P2", "title": "Discipline Daily", "author": "Author B",
     "categories": ["Books", "Self-Help"], "details": {"format": "Kindle"}, "price": "4.99"},
    {"parent_asin": "P3", "title": "Cooking 101", "author": "Chef C",
     "categories": ["Books", "Cooking"]},  # off-subject -> filtered out
]

REVIEWS = [
    FakeRv("P1", 2, "translation is clunky and dated", helpful=10, user="a"),
    FakeRv("P1", 3, "okay but the examples are weak", helpful=5, user="b"),
    FakeRv("P1", 1, "felt outdated throughout", helpful=8, user="c"),
    FakeRv("P1", 5, "loved it", helpful=1, user="d"),
    FakeRv("P1", 4, "pretty good", helpful=0, user="e"),
    FakeRv("P2", 1, "too basic to be useful", helpful=2, user="f"),
    FakeRv("P2", 2, "repetitive and shallow", helpful=1, user="g"),
    FakeRv("P3", 1, "should be filtered", helpful=99, user="z"),  # off-subject
]


def _build(min_critical_per_work=2):
    return build_seed_plan(
        META, REVIEWS, embedder=FakeEmbedder(), labeler=FakeLabeler(),
        subject_keywords=["philosophy", "self-help"],  # matched against category path
        cap_per_work=15, longtail_share=0.3, min_sample_gate=3,
        min_critical_per_work=min_critical_per_work,
        trigram_threshold=0.6, max_works=2,
    )


def test_selects_both_works_with_longtail():
    plan = _build()
    assert plan.counts["works_selected"] == 2
    titles = {w.title for w in plan.works}
    assert titles == {"Meditations", "Discipline Daily"}


def test_min_critical_floor_excludes_thin_works():
    # P1 (Meditations) has 3 critical reviews; P2 (Discipline Daily) has 2.
    # With the floor at 3, P2 is below it and must be excluded (§6.1.4): a work
    # that can only produce HDBSCAN noise is never selected.
    plan = _build(min_critical_per_work=3)
    assert {w.title for w in plan.works} == {"Meditations"}
    assert all(r.work_key for r in plan.reviews)
    assert all(r.edition_asin != "P2" for r in plan.reviews)


def test_off_subject_work_excluded():
    plan = _build()
    assert all(w.title != "Cooking 101" for w in plan.works)
    # the P3 review must never be ingested
    assert all(r.edition_asin != "P3" for r in plan.reviews)


def test_only_critical_reviews_kept_with_embeddings():
    plan = _build()
    assert plan.reviews, "expected critical reviews"
    assert all(r.rating <= 3 for r in plan.reviews)
    assert all(r.embedding is not None and len(r.embedding) == 4 for r in plan.reviews)


def test_editions_and_sentiment_proxy():
    plan = _build()
    assert {e.asin for e in plan.editions} == {"P1", "P2"}
    # rating 1 -> sentiment -1.0 (clamped), rating 3 -> 0.0
    by_rating = {r.rating: r.sentiment for r in plan.reviews}
    assert by_rating[1.0] == -1.0
    assert by_rating[3.0] == 0.0
