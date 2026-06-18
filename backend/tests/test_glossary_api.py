from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_detect_terms_unauthorized():
    resp = client.post("/api/glossary/detect", json={"text": "五位一体"})
    assert resp.status_code == 401
