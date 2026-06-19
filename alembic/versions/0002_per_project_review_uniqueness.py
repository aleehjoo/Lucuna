"""per-project review uniqueness (PRD §17.10)

Replace the global reviews unique key (platform, external_id) with a
per-project key (project_id, platform, external_id). The global key
contradicted the multi-project isolation requirement: the same Amazon
review can be relevant to two overlapping niches and must be storable
under each project independently.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-19
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_OLD = "reviews_platform_external_id_key"
_NEW = "reviews_project_platform_external_id_key"


def upgrade() -> None:
    op.execute(f"alter table reviews drop constraint if exists {_OLD}")
    op.execute(
        f"alter table reviews add constraint {_NEW} "
        f"unique (project_id, platform, external_id)")


def downgrade() -> None:
    op.execute(f"alter table reviews drop constraint if exists {_NEW}")
    op.execute(
        f"alter table reviews add constraint {_OLD} "
        f"unique (platform, external_id)")
