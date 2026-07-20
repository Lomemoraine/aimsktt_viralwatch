from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_earlywarning_endpoint():
    response = client.get("/earlywarning")
    assert response.status_code == 200
    payload = response.json()
    assert payload["n_zones"] > 0
    assert payload["watchlist"][0]["warning_score"] >= payload["watchlist"][-1]["warning_score"]
    assert any(item["borders_rwanda"] for item in payload["watchlist"])


def test_predict_endpoint():
    response = client.get("/predict/Goma")
    assert response.status_code == 200
    payload = response.json()
    assert payload["zone"] == "Goma"
    assert 0 <= payload["next7d_case_probability"] <= 1
    assert "model" in payload["note"].lower()


def test_briefing_endpoint():
    response = client.get("/briefing")
    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "source" in payload
