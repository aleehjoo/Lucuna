# tests/seed/test_config_knob.py
from lacuna.config import load_advanced

def test_works_trigram_threshold_present():
    adv = load_advanced()
    assert adv.get("works_trigram_threshold") == 0.6
