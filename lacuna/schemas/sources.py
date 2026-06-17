# lacuna/schemas/sources.py
"""Pydantic v2 boundary models. A source changing shape fails loud here (PRD §15)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class HardcoverReview(BaseModel):
    id: int
    rating: float | None = None
    body: str | None = None
    user_id: int | None = None
    created_at: datetime | None = None


class GoogleVolume(BaseModel):
    title: str
    categories: list[str] = Field(default_factory=list)
    average_rating: float | None = None
    ratings_count: int = 0

    @classmethod
    def model_validate(cls, obj, **kw):  # accept raw Google volume shape
        if isinstance(obj, dict) and "volumeInfo" in obj:
            vi = obj["volumeInfo"]
            obj = {
                "title": vi.get("title", ""),
                "categories": vi.get("categories", []),
                "average_rating": vi.get("averageRating"),
                "ratings_count": vi.get("ratingsCount", 0),
            }
        return super().model_validate(obj, **kw)


class NytBestseller(BaseModel):
    title: str
    weeks_on_list: int = 0
    rank: int | None = None


class OpenLibraryDoc(BaseModel):
    title: str
    first_publish_year: int | None = None
    edition_count: int = 0


class CorpusReview(BaseModel):
    """One McAuley raw_review_Books row (subset we keep)."""
    asin: str
    parent_asin: str | None = None
    rating: float
    title: str | None = None
    text: str
    helpful_vote: int = 0
    timestamp: int | None = None  # epoch ms
    user_id: str | None = None

    @field_validator("rating")
    @classmethod
    def rating_in_range(cls, v: float) -> float:
        if not 0 <= v <= 5:
            raise ValueError(f"rating {v} out of 0–5")
        return v

    @property
    def review_date(self) -> datetime | None:
        from datetime import timezone
        return datetime.fromtimestamp(self.timestamp / 1000, tz=timezone.utc) if self.timestamp else None
