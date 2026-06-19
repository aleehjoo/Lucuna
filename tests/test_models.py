# tests/test_models.py
from lacuna.db.models import Base

EXPECTED = {
    "projects", "works", "editions", "reviews", "aspect_clusters",
    "demand_signals", "supply_signals", "scores", "taxonomy_crosswalk",
    "unmapped_labels", "analysis_runs",
}

def test_all_prd_tables_mapped():
    assert EXPECTED.issubset(set(Base.metadata.tables)), \
        set(Base.metadata.tables).symmetric_difference(EXPECTED)

def test_reviews_has_384_dim_vector():
    col = Base.metadata.tables["reviews"].c["embedding"]
    # pgvector Vector stores dim on the type
    assert getattr(col.type, "dim", None) == 384

def test_job_model_columns():
    from lacuna.db.models import Job
    cols = Job.__table__.columns
    assert {"id", "project_id", "kind", "status", "progress_pct", "step",
            "counts", "result_ref", "error_detail", "created_at", "updated_at"} <= set(cols.keys())
    assert Job.__tablename__ == "jobs"
