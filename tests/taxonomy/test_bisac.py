# tests/taxonomy/test_bisac.py
from lacuna.taxonomy.bisac import is_valid_bisac, canonical_label, SEED_BISAC

def test_format_validation():
    assert is_valid_bisac("SEL036000") is True
    assert is_valid_bisac("PHI011000") is True
    assert is_valid_bisac("sel036000") is False   # must be uppercase 3 letters + 6 digits
    assert is_valid_bisac("SEL36000") is False     # wrong digit count
    assert is_valid_bisac("") is False

def test_seed_labels_present_and_resolvable():
    assert "SEL036000" in SEED_BISAC
    assert canonical_label("SEL036000")  # non-empty
    assert canonical_label("ZZZ999999") is None   # unknown code
