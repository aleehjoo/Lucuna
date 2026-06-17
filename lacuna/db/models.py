# lacuna/db/models.py
"""SQLAlchemy 2.0 ORM models for query/use. The DDL is owned by the alembic
migration (Task A7) which reproduces PRD §5 verbatim; these models mirror it.
Tables/columns must stay in sync with that migration."""
from __future__ import annotations

import datetime as dt
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY, BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=sa_text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_bisac: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    subject_filter: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'"))
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))


class Work(Base):
    __tablename__ = "works"
    __table_args__ = (UniqueConstraint("project_id", "normalized_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=sa_text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    normalized_key: Mapped[str] = mapped_column(Text, nullable=False)
    norm_version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text)
    primary_bisac: Mapped[str | None] = mapped_column(Text)
    first_pub_year: Mapped[int | None] = mapped_column(Integer)
    edition_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("0"))
    agg_rating_avg: Mapped[float | None] = mapped_column(Numeric(3, 2))
    agg_rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("0"))
    agg_rating_bayes: Mapped[float | None] = mapped_column(Numeric(3, 2))


class Edition(Base):
    __tablename__ = "editions"
    __table_args__ = (
        UniqueConstraint("project_id", "asin"),
        CheckConstraint("format in ('kindle','paperback','hardcover','audiobook','other')"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=sa_text("gen_random_uuid()"))
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asin: Mapped[str | None] = mapped_column(Text)
    parent_asin: Mapped[str | None] = mapped_column(Text)
    isbn13: Mapped[str | None] = mapped_column(Text)
    isbn10: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int | None] = mapped_column(Integer)
    rating_avg: Mapped[float | None] = mapped_column(Numeric(3, 2))
    rating_count: Mapped[int | None] = mapped_column(Integer)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("platform", "external_id"),
        CheckConstraint("platform in ('amazon_corpus','hardcover')"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), nullable=False)
    edition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("editions.id", ondelete="SET NULL"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1))
    helpful_votes: Mapped[int | None] = mapped_column(Integer)
    review_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    aspect_cluster_id: Mapped[int | None] = mapped_column(BigInteger)
    sentiment: Mapped[float | None] = mapped_column(Numeric(4, 3))
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))


class AspectCluster(Base):
    __tablename__ = "aspect_clusters"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    work_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    bisac_code: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_count: Mapped[int] = mapped_column(Integer, nullable=False)
    helpful_weight: Mapped[float | None] = mapped_column(Numeric(6, 3))
    platforms: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    cross_platform: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    representative: Mapped[str | None] = mapped_column(Text)


class DemandSignal(Base):
    __tablename__ = "demand_signals"
    __table_args__ = (CheckConstraint("source in ('nyt','googlebooks','hardcover')"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    bisac_code: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)


class SupplySignal(Base):
    __tablename__ = "supply_signals"
    __table_args__ = (CheckConstraint("source in ('openlibrary','googlebooks')"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    bisac_code: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    title_count: Mapped[int | None] = mapped_column(Integer)
    recent_title_count: Mapped[int | None] = mapped_column(Integer)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("project_id", "scope", "ref_id"),
        CheckConstraint("scope in ('work','bisac')"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    ref_id: Mapped[str] = mapped_column(Text, nullable=False)
    demand_score: Mapped[float | None] = mapped_column(Numeric(5, 3))
    supply_scarcity: Mapped[float | None] = mapped_column(Numeric(5, 3))
    unmet_need: Mapped[float | None] = mapped_column(Numeric(5, 3))
    gap_score: Mapped[float | None] = mapped_column(Numeric(5, 3))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    platforms_used: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    oldest_signal: Mapped[dt.date | None] = mapped_column(Date)
    newest_signal: Mapped[dt.date | None] = mapped_column(Date)
    incomplete: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    blind_spot: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    recent_supply_surge: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))


class TaxonomyCrosswalk(Base):
    __tablename__ = "taxonomy_crosswalk"
    __table_args__ = (
        UniqueConstraint("source", "source_label"),
        CheckConstraint("source in ('openlibrary','nyt','amazon','googlebooks')"),
        CheckConstraint("origin in ('prebuilt','learned','manual')"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_bisac: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default=sa_text("1.0"))
    origin: Mapped[str] = mapped_column(Text, nullable=False)


class UnmappedLabel(Base):
    __tablename__ = "unmapped_labels"
    __table_args__ = (UniqueConstraint("project_id", "source", "source_label"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(Text, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("1"))
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (CheckConstraint("mode in ('single_title','category_sweep','seed','validation')"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str | None] = mapped_column(Text)
    sources_used: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sa_text("'running'"))
    counts: Mapped[dict | None] = mapped_column(JSONB)
    error_detail: Mapped[str | None] = mapped_column(Text)
