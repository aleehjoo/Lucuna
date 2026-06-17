# tests/seed/test_edition_extraction.py
from lacuna.seed.seed import edition_from_meta, infer_format

def test_infer_format_from_text():
    assert infer_format("Kindle Edition") == "kindle"
    assert infer_format("Paperback") == "paperback"
    assert infer_format("Audible Audiobook") == "audiobook"
    assert infer_format("Mass Market") == "other"

def test_edition_from_meta_extracts_fields():
    row = {"parent_asin": "P1", "asin": "A1", "title": "Meditations",
           "author": {"name": "Aurelius"}, "price": "12.99",
           "details": {"format": "Paperback"}}
    ed = edition_from_meta(row)
    assert ed.asin == "A1" and ed.parent_asin == "P1"
    assert ed.price_cents == 1299
    assert ed.format == "paperback"

def test_edition_from_meta_tolerates_missing_price():
    ed = edition_from_meta({"asin": "A2", "title": "X"})
    assert ed.price_cents is None and ed.format == "other"
