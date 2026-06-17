# tests/export/test_narrative.py
from lacuna.export.narrative import maybe_add_narrative

def test_no_key_returns_pack_unchanged():
    pack = {"candidates": []}
    out = maybe_add_narrative(pack, api_key=None)
    assert out is pack and "narrative" not in out

def test_with_key_uses_injected_client_and_sees_only_pack():
    seen = {}
    def fake_caller(api_key, pack):
        seen["pack"] = pack
        return "Summary: two strong hypotheses."
    pack = {"candidates": [{"title_or_subject": "X"}]}
    out = maybe_add_narrative(pack, api_key="sk-test", _caller=fake_caller)
    assert out["narrative"].startswith("Summary")
    assert seen["pack"] is pack  # only the aggregated pack passed, no raw reviews
