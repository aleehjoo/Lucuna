# tests/taxonomy/test_crosswalk.py
import pytest
from lacuna.taxonomy.crosswalk import classify_match, best_match, MatchDecision

def test_classify_accept_reject_queue():
    assert classify_match(0.90, accept=0.85, reject=0.55) == MatchDecision.ACCEPT
    assert classify_match(0.85, accept=0.85, reject=0.55) == MatchDecision.ACCEPT  # boundary inclusive
    assert classify_match(0.70, accept=0.85, reject=0.55) == MatchDecision.QUEUE
    assert classify_match(0.55, accept=0.85, reject=0.55) == MatchDecision.QUEUE   # >= reject -> queue
    assert classify_match(0.40, accept=0.85, reject=0.55) == MatchDecision.REJECT

def test_best_match_picks_highest_similarity():
    sims = {"SEL036000": 0.62, "PHI011000": 0.91, "BUS019000": 0.30}
    code, sim = best_match(sims)
    assert code == "PHI011000" and sim == 0.91

def test_best_match_empty_returns_none():
    assert best_match({}) == (None, 0.0)
