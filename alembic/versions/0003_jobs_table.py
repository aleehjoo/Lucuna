"""jobs table — UI-facing async status surface (Frontend PRD §5)

Adds the single new table the frontend PRD permits. No other schema change.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-19
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_DDL = """
create table if not exists jobs (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid references projects(id) on delete cascade,
  kind         text not null check (kind in ('seed','live_search','sweep')),
  status       text not null default 'queued' check (status in ('queued','running','done','error')),
  progress_pct numeric(5,2) not null default 0,
  step         text,
  counts       jsonb,
  result_ref   text,
  error_detail text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists jobs_project_idx on jobs (project_id, created_at desc);
"""


def _split(sql: str) -> list[str]:
    # This DDL has no dollar-quoted bodies, so splitting on ';' is safe.
    return [s.strip() for s in sql.split(";") if s.strip()]


def upgrade() -> None:
    # asyncpg uses the extended (prepared-statement) protocol, which rejects
    # multiple commands per execute — so run each statement individually
    # (same fix as migration 0001).
    for stmt in _split(_DDL):
        op.execute(stmt)


def downgrade() -> None:
    op.execute("drop table if exists jobs")
