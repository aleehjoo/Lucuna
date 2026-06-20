# tests/seed/test_seed_progress_cb.py
"""run_seed must thread an optional progress_cb through to the orchestrator's
existing progress points without altering seed math/counts (Task 8). The heavy
internals (corpus iterators, Embedder, AspectLabeler, DB persistence) are
stubbed via the real internal entry point run_seed delegates to."""
from __future__ import annotations

from lacuna.seed import seed as seed_mod


def test_run_seed_invokes_progress_cb(monkeypatch):
    """run_seed must call progress_cb at its logging points without altering
    counts. We stub the heavy internals and assert the callback sees
    step/progress updates, and that the returned counts pass through unchanged."""
    events = []

    def fake_build_and_persist(*, rebuild, max_works, meta_limit, review_limit,
                               progress_cb=None, **_kw):
        if progress_cb:
            progress_cb({"step": "meta", "progress_pct": 10.0,
                        "counts": {"meta_scanned": 25000}})
            progress_cb({"step": "clustering", "progress_pct": 90.0,
                        "counts": {"clusters": 2}})
        return {"clusters": 2, "works_selected": 6}

    # _build_and_persist is the real internal entry run_seed delegates to
    # (build_seed_plan + persist_seed_plan + record_run), confirmed by reading
    # lacuna/seed/seed.py. Stubbing it avoids touching corpus/models/DB.
    monkeypatch.setattr(seed_mod, "_build_and_persist", fake_build_and_persist)

    counts = seed_mod.run_seed(rebuild=True, max_works=1, meta_limit=1, review_limit=1,
                               progress_cb=lambda e: events.append(e))

    assert any(e["step"] == "clustering" for e in events)
    assert any(e["step"] == "meta" for e in events)
    assert counts["clusters"] == 2
    assert counts["works_selected"] == 6


def test_run_seed_without_progress_cb_is_unaffected(monkeypatch):
    """Omitting progress_cb (existing CLI call shape) must keep working — the
    parameter is additive, not required."""
    def fake_build_and_persist(*, rebuild, max_works, meta_limit, review_limit,
                               progress_cb=None, **_kw):
        assert progress_cb is None
        return {"clusters": 0, "works_selected": 0}

    monkeypatch.setattr(seed_mod, "_build_and_persist", fake_build_and_persist)

    counts = seed_mod.run_seed(rebuild=True, max_works=1, meta_limit=1, review_limit=1)
    assert counts == {"clusters": 0, "works_selected": 0}
