# tests/test_migration_sql.py
from pathlib import Path

MIG = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0001_initial_schema.py"
MIG_0003 = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0003_jobs_table.py"

def test_migration_enables_pgvector_and_core_tables():
    sql = MIG.read_text(encoding="utf-8")
    assert "create extension if not exists vector" in sql.lower()
    for table in ("projects", "works", "editions", "reviews", "scores",
                  "aspect_clusters", "demand_signals", "supply_signals",
                  "taxonomy_crosswalk", "unmapped_labels", "analysis_runs"):
        assert f"create table {table}" in sql.lower(), table
    assert "ivfflat" in sql.lower()
    assert "vector(384)" in sql.lower()

def test_no_reddit_or_docker_anywhere_in_migration():
    sql = MIG.read_text(encoding="utf-8").lower()
    assert "reddit" not in sql
    assert "docker" not in sql

def test_jobs_migration_creates_table_and_index():
    src = MIG_0003.read_text(encoding="utf-8")
    sql = src.lower()
    assert "create table" in sql and "jobs" in sql
    assert "check (kind in ('seed','live_search','sweep'))" in sql
    assert "jobs_project_idx" in sql
    assert 'revision = "0003"' in src and 'down_revision = "0002"' in src
