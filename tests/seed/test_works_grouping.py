# tests/seed/test_works_grouping.py
from lacuna.seed.works_grouping import EditionInput, group_editions

def _ed(asin, parent, title, author):
    return EditionInput(asin=asin, parent_asin=parent, title=title, author=author)

def test_pass1_groups_by_parent_asin():
    eds = [_ed("A1", "P1", "Meditations", "Aurelius"),
           _ed("A2", "P1", "Meditations (Kindle)", "Aurelius")]
    groups = group_editions(eds)
    assert len(groups) == 1
    assert {e.asin for e in groups[0].members} == {"A1", "A2"}

def test_pass2_merges_by_normalized_key_across_parents():
    eds = [_ed("A1", "P1", "Meditations: A New Translation", "Marcus Aurelius"),
           _ed("A2", "P2", "Meditations (Paperback)", "Marcus Aurelius")]
    groups = group_editions(eds)
    assert len(groups) == 1

def test_pass3_keeps_separate_and_flags_when_below_trigram_threshold():
    eds = [_ed("A1", "P1", "Stoicism Today", "Smith"),
           _ed("A2", "P2", "Stoic Wisdom Forever", "Smith")]
    groups = group_editions(eds, trigram_threshold=0.6)
    # different titles, same surname, low trigram sim -> stay separate
    assert len(groups) == 2

def test_distinct_works_not_merged():
    eds = [_ed("A1", "P1", "Dune", "Herbert"),
           _ed("A2", "P2", "Meditations", "Aurelius")]
    assert len(group_editions(eds)) == 2
