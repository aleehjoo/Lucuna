import inspect

from lacuna.pipeline.distill import distill_score_export


def test_distill_accepts_project_id_param():
    sig = inspect.signature(distill_score_export)
    assert "project_id" in sig.parameters, "distiller must be id-aware for multi-project export"
    assert sig.parameters["project_id"].default is None  # CLI path unchanged when omitted
