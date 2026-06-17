# tests/test_pin_revisions.py
import textwrap
import pytest
from scripts import pin_revisions as pr

class FakeInfo:
    def __init__(self, sha): self.sha = sha

def test_resolve_writes_real_shas(tmp_path, monkeypatch):
    cfg = tmp_path / "advanced.yaml"
    cfg.write_text(textwrap.dedent("""
        models:
          embedding:  { name: "sentence-transformers/all-MiniLM-L6-v2", revision: "<resolved-at-build>" }
          zero_shot:  { name: "facebook/bart-large-mnli",               revision: "<resolved-at-build>" }
        dataset:
          amazon_reviews: { name: "McAuley-Lab/Amazon-Reviews-2023", revision: "<resolved-at-build>" }
    """), encoding="utf-8")
    monkeypatch.setattr(pr, "_model_sha", lambda name: "a" * 40)
    monkeypatch.setattr(pr, "_dataset_sha", lambda name: "b" * 40)
    pr.pin(cfg, verify=False)
    out = cfg.read_text(encoding="utf-8")
    assert "<resolved-at-build>" not in out
    assert "a" * 40 in out and "b" * 40 in out

def test_fail_loud_when_sha_unresolvable(tmp_path, monkeypatch):
    cfg = tmp_path / "advanced.yaml"
    cfg.write_text('models:\n  embedding: { name: "x", revision: "<resolved-at-build>" }\n', encoding="utf-8")
    monkeypatch.setattr(pr, "_model_sha", lambda name: None)
    with pytest.raises(SystemExit):
        pr.pin(cfg, verify=False)
