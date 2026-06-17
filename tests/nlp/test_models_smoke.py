# tests/nlp/test_models_smoke.py
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("LACUNA_RUN_MODEL_SMOKE") != "1",
    reason="set LACUNA_RUN_MODEL_SMOKE=1 to run heavy model smoke tests (downloads weights)",
)

def test_minilm_encodes_384():
    from lacuna.nlp.embeddings import Embedder, EMBED_DIM
    out = Embedder().encode(["a sentence", "another"])
    assert out.shape == (2, EMBED_DIM)

def test_bart_zero_shot_labels():
    from lacuna.nlp.aspects import AspectLabeler
    res = AspectLabeler().label_cluster(["the price is far too high for what you get"])
    assert res.label  # any taxonomy label
