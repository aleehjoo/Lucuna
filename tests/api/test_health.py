async def test_health_reports_models_ready(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["models_ready"] is True
    assert body["status"] == "ok"
