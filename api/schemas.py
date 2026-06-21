# api/schemas.py
"""API DTOs. The HTTP contract — deliberately decoupled from ORM rows, and never
carries a secret value (Frontend PRD §13.7)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    target_bisac: list[str] = Field(default_factory=list)
    subject_filter: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    """Partial update — Settings persists intent knobs into `config` (Frontend PRD
    §10). All fields optional; only provided fields are written."""
    name: str | None = None
    target_bisac: list[str] | None = None
    subject_filter: dict | None = None
    config: dict | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    target_bisac: list[str]
    subject_filter: dict
    config: dict
    seeded: bool
    work_count: int
    cluster_count: int
    created_at: str | None = None


class SearchRequest(BaseModel):
    title: str | None = None
    isbn: str | None = None


class SeedRequest(BaseModel):
    meta_limit: int = 200_000
    review_limit: int = 1_000_000
    max_works: int = 25


class JobOut(BaseModel):
    id: str
    project_id: str | None
    kind: str
    status: str
    progress_pct: float
    step: str | None = None
    counts: dict | None = None
    result_ref: str | None = None
    error_detail: str | None = None
