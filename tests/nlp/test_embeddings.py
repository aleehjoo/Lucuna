# tests/nlp/test_embeddings.py
import numpy as np
from lacuna.nlp.embeddings import Embedder, review_hash

def test_review_hash_stable_and_unique():
    assert review_hash("abc") == review_hash("abc")
    assert review_hash("abc") != review_hash("abd")

def test_embedder_uses_cache_and_calls_encoder_once_per_unique():
    calls = []
    def fake_encoder(texts):
        calls.append(list(texts))
        return np.array([[float(len(t))] * 3 for t in texts])
    emb = Embedder(encoder=fake_encoder)
    out1 = emb.encode(["hello", "hi"])
    out2 = emb.encode(["hello", "hi"])   # second call fully cached
    assert out1.shape == (2, 3)
    np.testing.assert_array_equal(out1, out2)
    # encoder called only for the first batch (both unique), not the cached second
    assert len(calls) == 1

def test_embedder_only_encodes_uncached_subset():
    calls = []
    def fake_encoder(texts):
        calls.append(list(texts)); return np.array([[1.0, 2.0, 3.0]] * len(texts))
    emb = Embedder(encoder=fake_encoder)
    emb.encode(["a"])
    emb.encode(["a", "b"])   # only "b" is new
    assert calls[-1] == ["b"]
