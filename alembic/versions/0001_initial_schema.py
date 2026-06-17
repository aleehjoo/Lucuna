"""initial schema (PRD §5) + pgvector

Revision ID: 0001
Revises:
Create Date: 2026-06-17
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = r"""
create extension if not exists vector;

create table projects (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  target_bisac   text[] not null,
  subject_filter jsonb not null default '{}',
  config         jsonb not null default '{}',
  created_at     timestamptz not null default now()
);

create table works (
  id              uuid primary key default gen_random_uuid(),
  project_id      uuid not null references projects(id) on delete cascade,
  normalized_key  text not null,
  norm_version    int not null,
  title           text not null,
  author          text,
  primary_bisac   text,
  first_pub_year  int,
  edition_count   int not null default 0,
  agg_rating_avg  numeric(3,2),
  agg_rating_count int not null default 0,
  agg_rating_bayes numeric(3,2),
  unique (project_id, normalized_key)
);

create table editions (
  id           uuid primary key default gen_random_uuid(),
  work_id      uuid not null references works(id) on delete cascade,
  project_id   uuid not null references projects(id) on delete cascade,
  asin         text,
  parent_asin  text,
  isbn13       text,
  isbn10       text,
  format       text check (format in ('kindle','paperback','hardcover','audiobook','other')),
  price_cents  int,
  rating_avg   numeric(3,2),
  rating_count int,
  unique (project_id, asin)
);

create table reviews (
  id            bigint generated always as identity primary key,
  work_id       uuid not null references works(id) on delete cascade,
  edition_id    uuid references editions(id) on delete set null,
  project_id    uuid not null references projects(id) on delete cascade,
  platform      text not null check (platform in ('amazon_corpus','hardcover')),
  external_id   text,
  rating        numeric(2,1),
  helpful_votes int,
  review_date   timestamptz,
  text          text,
  embedding     vector(384),
  aspect_cluster_id bigint,
  sentiment     numeric(4,3),
  processed     boolean not null default false,
  unique (platform, external_id)
);
create index reviews_work_idx on reviews (work_id);
create index reviews_embedding_idx on reviews using ivfflat (embedding vector_cosine_ops);

create table aspect_clusters (
  id             bigint generated always as identity primary key,
  project_id     uuid not null references projects(id) on delete cascade,
  work_id        uuid references works(id) on delete cascade,
  bisac_code     text,
  label          text not null,
  member_count   int not null,
  reviewer_count int not null,
  helpful_weight numeric(6,3),
  platforms      text[] not null,
  cross_platform boolean not null default false,
  representative text
);

create table demand_signals (
  id          bigint generated always as identity primary key,
  project_id  uuid not null references projects(id) on delete cascade,
  bisac_code  text not null,
  source      text not null check (source in ('nyt','googlebooks','hardcover')),
  metric      text not null,
  value       numeric,
  as_of_date  date not null
);

create table supply_signals (
  id                 bigint generated always as identity primary key,
  project_id         uuid not null references projects(id) on delete cascade,
  bisac_code         text not null,
  source             text not null check (source in ('openlibrary','googlebooks')),
  title_count        int,
  recent_title_count int,
  as_of_date         date not null
);

create table scores (
  id              bigint generated always as identity primary key,
  project_id      uuid not null references projects(id) on delete cascade,
  scope           text not null check (scope in ('work','bisac')),
  ref_id          text not null,
  demand_score    numeric(5,3),
  supply_scarcity numeric(5,3),
  unmet_need      numeric(5,3),
  gap_score       numeric(5,3),
  confidence      numeric(4,3) not null,
  sample_size     int not null,
  platforms_used  text[] not null,
  oldest_signal   date,
  newest_signal   date,
  incomplete      boolean not null default false,
  blind_spot      boolean not null default false,
  recent_supply_surge boolean not null default false,
  computed_at     timestamptz not null default now(),
  unique (project_id, scope, ref_id)
);

create table taxonomy_crosswalk (
  id              bigint generated always as identity primary key,
  canonical_bisac text not null,
  source          text not null check (source in ('openlibrary','nyt','amazon','googlebooks')),
  source_label    text not null,
  confidence      numeric(3,2) not null default 1.0,
  origin          text not null check (origin in ('prebuilt','learned','manual')),
  unique (source, source_label)
);

create table unmapped_labels (
  id           bigint generated always as identity primary key,
  project_id   uuid not null references projects(id) on delete cascade,
  source       text not null,
  source_label text not null,
  occurrences  int not null default 1,
  resolved     boolean not null default false,
  unique (project_id, source, source_label)
);

create table analysis_runs (
  id           bigint generated always as identity primary key,
  project_id   uuid references projects(id) on delete cascade,
  mode         text not null check (mode in ('single_title','category_sweep','seed','validation')),
  target       text,
  sources_used text[],
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  status       text not null default 'running',
  counts       jsonb,
  error_detail text
);
"""

DROP = """
drop table if exists analysis_runs, unmapped_labels, taxonomy_crosswalk, scores,
  supply_signals, demand_signals, aspect_clusters, reviews, editions, works, projects cascade;
"""


def _split(sql: str) -> list[str]:
    # This DDL has no dollar-quoted bodies, so splitting on ';' is safe.
    return [s.strip() for s in sql.split(";") if s.strip()]


def upgrade() -> None:
    # asyncpg uses the extended (prepared-statement) protocol, which rejects
    # multiple commands per execute — so run each statement individually.
    conn = op.get_bind()
    has_vector = conn.exec_driver_sql(
        "select count(*) from pg_extension where extname='vector'").scalar()
    for stmt in _split(DDL):
        # pgvector may already be enabled by an admin/dashboard and the app role
        # may lack CREATE EXTENSION; skip the no-op in that case.
        if stmt.lower().startswith("create extension") and has_vector:
            continue
        op.execute(stmt)


def downgrade() -> None:
    for stmt in _split(DROP):
        op.execute(stmt)
