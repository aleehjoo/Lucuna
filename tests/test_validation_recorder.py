# tests/test_validation_recorder.py
from lacuna.pipeline.validation import make_db_recorder, ValidationResult
from lacuna.db.models import AnalysisRun

class FakeSession:
    def __init__(self, sink): self._sink = sink
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    def add(self, obj): self._sink.append(obj)
    async def commit(self): pass

def fake_sessionmaker(sink):
    def _mk(): return FakeSession(sink)
    return _mk

async def test_recorder_writes_validation_run():
    sink = []
    recorder = make_db_recorder(sessionmaker=fake_sessionmaker(sink))
    await recorder(ValidationResult(True, "Atomic Habits", 12))
    assert len(sink) == 1
    run = sink[0]
    assert isinstance(run, AnalysisRun)
    assert run.mode == "validation"
    assert run.status == "ok"
    assert run.counts == {"review_count": 12}
    assert run.target == "Atomic Habits"

async def test_recorder_marks_error_status():
    sink = []
    recorder = make_db_recorder(sessionmaker=fake_sessionmaker(sink))
    await recorder(ValidationResult(False, "X", 0, error="no live reviews"))
    assert sink[0].status == "error"
    assert sink[0].error_detail == "no live reviews"
