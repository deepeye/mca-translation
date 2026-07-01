"""Test decisions API endpoints."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.api.deps import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.user import User


@pytest.fixture
def mock_user():
    return User(id=uuid.uuid4(), username="testuser", hashed_password="fakehash")


@pytest.mark.asyncio
async def test_list_result_decisions_returns_logs(mock_user):
    """GET /api/results/{result_id}/decisions should return decision logs."""
    result_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # Override auth & db deps — FastAPI holds the original function reference
    # in Depends(), so module-level patch() won't take effect; use overrides.
    async def fake_get_current_user():
        return mock_user

    async def fake_get_db():
        return None

    app.dependency_overrides[get_current_user] = fake_get_current_user
    app.dependency_overrides[get_db] = fake_get_db

    # Mock the service to return a fake log
    fake_log = type("FakeLog", (), {
        "id": uuid.uuid4(), "job_id": job_id, "result_id": result_id,
        "stage": "risk", "decision_type": "risk_identified",
        "source_phrase": None, "target_phrase": "bad",
        "decision": "标记为 high 风险", "reasoning": "原因",
        "confidence": "high", "metadata_": {"risk_level": "high"},
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    })()

    try:
        with patch("app.api.decisions._get_user_result",
                   AsyncMock(return_value=object())), \
             patch("app.api.decisions.get_decision_logs_by_result",
                   AsyncMock(return_value=[fake_log])):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get(f"/api/results/{result_id}/decisions")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["stage"] == "risk"
    assert data[0]["confidence"] == "high"


@pytest.mark.asyncio
async def test_list_result_decisions_empty_returns_empty_list(mock_user):
    """GET /api/results/{result_id}/decisions with no logs returns []."""
    result_id = uuid.uuid4()

    async def fake_get_current_user():
        return mock_user

    async def fake_get_db():
        return None

    app.dependency_overrides[get_current_user] = fake_get_current_user
    app.dependency_overrides[get_db] = fake_get_db

    try:
        with patch("app.api.decisions._get_user_result",
                   AsyncMock(return_value=object())), \
             patch("app.api.decisions.get_decision_logs_by_result",
                   AsyncMock(return_value=[])):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get(f"/api/results/{result_id}/decisions")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == []
