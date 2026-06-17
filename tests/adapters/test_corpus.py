# tests/adapters/test_corpus.py
from lacuna.adapters.corpus import iter_reviews, CORPUS_NAME

FAKE_ROWS = [
    {"asin": "B1", "parent_asin": "P1", "rating": 2.0, "title": "meh",
     "text": "examples are outdated", "helpful_vote": 9, "timestamp": 1_600_000_000_000, "user_id": "u1"},
    {"asin": "B2", "parent_asin": "P1", "rating": 5.0, "title": "great",
     "text": "loved it", "helpful_vote": 0, "timestamp": 1_600_000_000_000, "user_id": "u2"},
]

def test_iter_reviews_validates_and_yields():
    out = list(iter_reviews(_source=iter(FAKE_ROWS)))
    assert len(out) == 2
    assert out[0].asin == "B1" and out[0].helpful_vote == 9
    assert out[0].review_date is not None

def test_corpus_name_is_mcauley():
    assert CORPUS_NAME == "McAuley-Lab/Amazon-Reviews-2023"
