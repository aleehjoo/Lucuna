from api.runtime import EngineRuntime


class _FakeEmbedder:
    def encode(self, texts):
        return [[0.0] for _ in texts]


class _FakeLabeler:
    def label_cluster(self, texts, candidate_labels=None):
        return None


def test_runtime_holds_injected_components_without_loading_models():
    rt = EngineRuntime.for_testing(embedder=_FakeEmbedder(), labeler=_FakeLabeler())
    assert rt.embedder is not None
    assert rt.labeler is not None
    # injected components must be used verbatim (no model download in tests)
    assert rt.embedder.encode(["x"]) == [[0.0]]
