# tests/nlp/test_aspects.py
from lacuna.nlp.aspects import AspectLabeler, ASPECT_TAXONOMY, pick_aspect

def test_aspect_taxonomy_matches_prd():
    assert ASPECT_TAXONOMY == [
        "outdated", "too_basic", "too_advanced", "poor_examples",
        "inaccurate", "badly_structured", "overpriced", "repetitive",
    ]

def test_pick_aspect_returns_highest():
    label, score = pick_aspect({"outdated": 0.2, "overpriced": 0.7, "repetitive": 0.1})
    assert label == "overpriced" and score == 0.7

def test_labeler_labels_cluster_with_injected_classifier():
    # fake zero-shot: returns dict label->score for given texts
    def fake_clf(text, candidate_labels):
        return {lab: (0.9 if lab == "outdated" else 0.05) for lab in candidate_labels}
    labeler = AspectLabeler(classifier=fake_clf)
    result = labeler.label_cluster(["the examples are from 2009", "outdated references"])
    assert result.label == "outdated"
    assert result.score >= 0.5
    # representative is a paraphrase, never a raw quote
    assert "examples are from 2009" not in result.representative
