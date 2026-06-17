# tests/seed/test_normalization.py
from lacuna.seed.normalization import (
    NORM_VERSION, normalize_title, normalize_author, normalized_key, author_surname,
)

def test_norm_version_is_int():
    assert isinstance(NORM_VERSION, int) and NORM_VERSION >= 1

def test_title_strips_subtitle_format_and_punct():
    # subtitle after ':' dropped, format token removed, punctuation/case normalized
    assert normalize_title("Meditations: A New Translation (Kindle Edition)") == "meditations"

def test_title_collapses_whitespace_and_series_tokens():
    assert normalize_title("Dune   Book  1") == "dune 1"

def test_author_surname_extracted():
    assert author_surname("Marcus Aurelius") == "aurelius"
    assert author_surname("") == ""

def test_normalized_key_combines_title_and_author():
    assert normalized_key("Meditations: X", "Marcus Aurelius") == "meditations|marcus aurelius"

def test_normalize_author_handles_none():
    assert normalize_author(None) == ""
