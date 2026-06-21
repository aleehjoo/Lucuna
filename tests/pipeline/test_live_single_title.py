import numpy as np

from lacuna.aggregation.cross_platform import AspectClusterIn
from lacuna.nlp.aspects import AspectResult
from lacuna.pipeline.live_single_title import analyze_live


class FakeHardcoverReview:
    def __init__(self, rating, body, created_at=None):
        self.rating = rating; self.body = body; self.created_at = created_at


class FakeHardcoverBook:
    def __init__(self, title, reviews):
        self.id = 1; self.title = title; self.reviews = reviews


class FakeHardcover:
    def __init__(self, book):
        self._book = book
    async def fetch_book_by_title(self, title, *, review_limit=50):
        return self._book
    async def aclose(self):
        pass


class FakeEmbedder:
    def encode(self, texts):
        # cluster by length parity so 2 clear groups form
        return np.array([[float(len(t) % 2), float(len(t)), 0.0, 0.0] for t in texts])


class FakeLabeler:
    def label_cluster(self, texts, candidate_labels=None):
        return AspectResult(label="outdated", score=0.9,
                            representative="Readers say the material feels outdated.")


async def test_live_analysis_fresh_only_builds_pack():
    book = FakeHardcoverBook("Some Title", [
        FakeHardcoverReview(2, "the examples are outdated and old"),
        FakeHardcoverReview(1, "outdated material throughout the book"),
        FakeHardcoverReview(2, "felt dated and behind the times now"),
    ])
    result = await analyze_live(
        title="Some Title", hardcover=FakeHardcover(book),
        embedder=FakeEmbedder(), labeler=FakeLabeler(),
        seeded_clusters=None, cluster_min_size=2)
    assert result["fresh_only"] is True
    assert result["review_count"] == 3
    assert "candidates" in result["pack"]
    assert result["agreement_pct"] == 0.0  # single platform -> no cross-platform agreement

    # Ratings: 2, 1, 2 -> avg 1.67, all 3 carry a rating, bucketed by floor(r)
    # clamped to [1, 5]: two reviews floor to "2", one floors to "1".
    assert result["rating_avg"] == 1.67
    assert result["rating_count"] == 3
    assert result["rating_distribution"] == {"1": 1, "2": 2, "3": 0, "4": 0, "5": 0}


async def test_live_analysis_merges_with_seeded_raises_agreement():
    # Real HDBSCAN (via cluster_embeddings) needs a density CONTRAST between >=2
    # groups of size >= min_cluster_size to ever pick a non-noise cluster over background
    # noise (see tests/nlp/test_clustering.py) -- a lone pair or trio is always noise.
    # Build two length-parity groups of 5 (FakeEmbedder clusters on len(text) % 2) so the
    # fresh layer reliably yields real clusters instead of all-noise.
    base = "outdated material in this book feels old"
    even_group = [base + ("." * i) for i in (0, 2, 4, 6, 8)]
    odd_group = [base + ("." * i) for i in (1, 3, 5, 7, 9)]
    book = FakeHardcoverBook("Seeded Title", [
        FakeHardcoverReview(2, body) for body in even_group + odd_group
    ])
    seeded = [AspectClusterIn(label="outdated", platform="amazon_corpus",
                              reviewer_count=40, helpful_weight=12.0, member_count=44)]
    result = await analyze_live(
        title="Seeded Title", hardcover=FakeHardcover(book),
        embedder=FakeEmbedder(), labeler=FakeLabeler(),
        seeded_clusters=seeded, cluster_min_size=2)
    assert result["fresh_only"] is False
    # the merged "outdated" cluster now spans hardcover + amazon_corpus
    assert any(c.get("cross_platform") for c in result["clusters"])


async def test_live_analysis_no_rated_reviews_yields_null_average():
    # All reviews carry no rating at all (rating=None) -- the rating summary
    # must report an honest null average, not a fabricated 0.
    book = FakeHardcoverBook("Unrated Title", [
        FakeHardcoverReview(None, "the examples are outdated and old"),
        FakeHardcoverReview(None, "outdated material throughout the book"),
    ])
    result = await analyze_live(
        title="Unrated Title", hardcover=FakeHardcover(book),
        embedder=FakeEmbedder(), labeler=FakeLabeler(),
        seeded_clusters=None, cluster_min_size=2)
    assert result["rating_avg"] is None
    assert result["rating_count"] == 0
    assert result["rating_distribution"] == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
