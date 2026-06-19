import httpx
import pytest

from api.app import create_app
from api.runtime import EngineRuntime


class FakeEmbedder:
    def encode(self, texts):
        import numpy as np
        return np.array([[float(len(t)), 1.0, 0.0, 0.0] for t in texts])


class FakeLabeler:
    def label_cluster(self, texts, candidate_labels=None):
        from lacuna.nlp.aspects import AspectResult
        return AspectResult(label="outdated", score=0.9,
                            representative="Readers say the material feels outdated.")


@pytest.fixture
def runtime():
    return EngineRuntime.for_testing(embedder=FakeEmbedder(), labeler=FakeLabeler())


@pytest.fixture
async def client(runtime):
    app = create_app(runtime=runtime, sessionmaker=None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
