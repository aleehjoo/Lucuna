# tests/taxonomy/test_crosswalk_knob.py
from lacuna.config import load_advanced

def test_crosswalk_reject_knob_present():
    adv = load_advanced()
    assert adv.get("crosswalk_auto_accept") == 0.85
    assert adv.get("crosswalk_auto_reject") == 0.55
