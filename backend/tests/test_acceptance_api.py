# backend/tests/test_acceptance_api.py
import json
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.job import TranslationJob, TranslationResult
from app.services import acceptance_scorer as scorer_mod


@pytest.fixture
def mock_user():
    return User(id=uuid.uuid4(), username=f"acc_user_{uuid.uuid4().hex[:8]}", hashed_password="x")


class FakeClient:
    def __init__(self, content):
        self.content = content
    async def chat(self, *, model, messages, temperature=0.3):
        return {"content": self.content}


def _payload():
    return json.dumps({
        "audience": 20, "cultural": 20, "naturalness": 20, "risk": 20,
        "risk_phrase_offsets": [[0, 5]],
        "affects_neighbors": False,
        "rationale": "ok",
    })


@pytest.mark.asyncio
async def test_first_scoring_returns_result(db, mock_user):
    # 先持久化 user，避免 translation_jobs.user_id → users.id 的 FK 违约
    db.add(mock_user)
    await db.commit()

    # seed job + result
    job = TranslationJob(user_id=mock_user.id, source_text="你好世界。", genre="political",
                         strategy="semantic_equivalence", target_languages=["zh"])
    db.add(job); await db.commit(); await db.refresh(job)
    result = TranslationResult(job_id=job.id, language="zh",
                               translated_text="Hello world.", acceptance_score=-1)
    db.add(result); await db.commit(); await db.refresh(result)

    fake_db = db  # 直接复用 db fixture 的真实 session（route 会 commit/refresh）
    async def fake_get_db():
        yield fake_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = fake_get_db
    # patch bailian_client inside scorer（scorer 运行时惰性取模块全局，故 monkeypatch 生效）
    orig = scorer_mod.bailian_client
    scorer_mod.bailian_client = FakeClient(_payload())
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            res = await c.post(f"/api/jobs/{job.id}/acceptance-score",
                               json={"lang": "zh", "audience_baseline": "policy_media"})
        assert res.status_code == 200
        body = res.json()
        assert body["total_score"] == 80
        assert body["audience_baseline"] == "policy_media"
        assert "top3_risk_indices" in body
    finally:
        scorer_mod.bailian_client = orig
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delta_rescoring_updates_score(db, mock_user):
    # 先持久化 user，避免 translation_jobs.user_id → users.id 的 FK 违约
    db.add(mock_user)
    await db.commit()

    job = TranslationJob(user_id=mock_user.id, source_text="你好。再见。", genre="political",
                         strategy="semantic_equivalence", target_languages=["zh"])
    db.add(job); await db.commit(); await db.refresh(job)
    result = TranslationResult(
        job_id=job.id, language="zh",
        translated_text="Hello. Bye.",
        acceptance_score=80, audience_baseline="policy_media",
        acceptance_confidence=0.9,
        acceptance_dimensions={"audience": 20, "cultural": 20, "naturalness": 20, "risk": 20},
        acceptance_sentence_scores=[
            {"sentence_id": "s0", "dimensions": {"audience": 20, "cultural": 20, "naturalness": 20, "risk": 20},
             "confidence": 0.9, "risk_phrase_offsets": [], "affects_neighbors": False, "rationale": "ok", "failed": False},
            {"sentence_id": "s1", "dimensions": {"audience": 20, "cultural": 20, "naturalness": 20, "risk": 20},
             "confidence": 0.9, "risk_phrase_offsets": [], "affects_neighbors": False, "rationale": "ok", "failed": False},
        ],
    )
    db.add(result); await db.commit(); await db.refresh(result)

    async def fake_get_db():
        yield db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = fake_get_db
    # delta re-scores s1 to a lower score
    orig = scorer_mod.bailian_client
    scorer_mod.bailian_client = FakeClient(json.dumps({
        "audience": 10, "cultural": 10, "naturalness": 10, "risk": 10,
        "risk_phrase_offsets": [], "affects_neighbors": False, "rationale": "worse",
    }))
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            res = await c.post(f"/api/jobs/{job.id}/acceptance-score/delta",
                               json={"lang": "zh", "sentence_id": "s1", "new_text": "Bye."})
        assert res.status_code == 200
        body = res.json()
        # s1 dropped 80→40, s0 stays 80 → mean 60
        assert body["total_score"] == 60
    finally:
        scorer_mod.bailian_client = orig
        app.dependency_overrides.clear()
