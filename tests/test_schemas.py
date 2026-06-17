# tests/test_schemas.py
import pytest
from pydantic import ValidationError
from lacuna.schemas.sources import (
    HardcoverReview, GoogleVolume, NytBestseller, OpenLibraryDoc, CorpusReview,
)

def test_hardcover_review_parses_minimal():
    r = HardcoverReview(id=1, rating=2.0, body="weak examples", user_id=7)
    assert r.rating == 2.0 and r.user_id == 7

def test_google_volume_extracts_ratings_count():
    v = GoogleVolume.model_validate({
        "volumeInfo": {"title": "X", "categories": ["Self-Help / Personal Growth"],
                       "averageRating": 4.1, "ratingsCount": 12},
    })
    assert v.ratings_count == 12 and v.categories == ["Self-Help / Personal Growth"]

def test_shape_drift_fails_loud():
    with pytest.raises(ValidationError):
        NytBestseller.model_validate({"unexpected": "shape"})
