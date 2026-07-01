# backend/tests/test_acceptance_integration.py
import json
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.job import TranslationJob, TranslationResult
from app.models.decision_log import DecisionLog
from app.services import acceptance_scorer as scorer_mod


class FakeClient:
    """每次 chat 返回当前 content（同一句多次采样会拿到相同值 → confidence=1.0）。"""
    def __init__(self, content):
        self.content = content
    async def chat(self, *, model, messages, temperature=0.3):
        return {"content": self.content}


def _p(a=20, c=20, n=20, r=20, neighbors=False):
    return json.dumps({
        "audience": a, "cultural": c, "naturalness": n, "risk": r,
        "risk_phrase_offsets": [], "affects_neighbors": neighbors,
        "rationale": "integ",
    })


@pytest.mark.asyncio
async def test_full_chain_first_then_delta(db):
    # Seed: user → job → result (translated_text="Hello. Bye." → 2 sentences)
    user = User(id=uuid.uuid4(), username=f"integ_{uuid.uuid4().hex[:6]}", hashed_password="x")
    db.add(user); await db.commit()
    job = TranslationJob(user_id=user.id, source_text="你好。再见。", genre="political",
                         strategy="semantic_equivalence", target_languages=["en"])
    db.add(job); await db.commit(); await db.refresh(job)
    result = TranslationResult(job_id=job.id, language="en", translated_text="Hello. Bye.",
                               acceptance_score=-1)
    db.add(result); await db.commit(); await db.refresh(result)
    job_id = job.id
    result_id = result.id

    # 让 route 复用同一 db session（route 会 commit/refresh）
    async def fake_get_db():
        yield db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = fake_get_db
    orig = scorer_mod.bailian_client
    # first scoring: 2 sentences, each dims 20×4 → score 80（多次采样同值 → confidence=1.0）
    scorer_mod.bailian_client = FakeClient(_p())
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            # 1. first scoring
            res = await c.post(f"/api/jobs/{job_id}/acceptance-score",
                               json={"lang": "en", "audience_baseline": "policy_media"})
            assert res.status_code == 200
            assert res.json()["total_score"] == 80

            # verify DB fields written
            res_obj = (await db.execute(
                select(TranslationResult).where(TranslationResult.id == result_id)
            )).scalar_one()
            assert res_obj.acceptance_score == 80
            assert res_obj.audience_baseline == "policy_media"
            assert res_obj.acceptance_confidence is not None
            assert res_obj.acceptance_sentence_scores is not None
            assert len(res_obj.acceptance_sentence_scores) == 2

            # verify decision_log entry (stage=acceptance, trigger=initial)
            logs = (await db.execute(
                select(DecisionLog).where(DecisionLog.result_id == result_id,
                                          DecisionLog.stage == "acceptance")
            )).scalars().all()
            assert len(logs) == 1
            assert logs[0].metadata_.get("trigger") == "initial"

            # 2. delta re-scoring: add a risk annotation in s1 (post-accept state), re-score s1 → 40
            from sqlalchemy.orm.attributes import flag_modified as _flag
            res_obj = (await db.execute(
                select(TranslationResult).where(TranslationResult.id == result_id)
            )).scalar_one()
            res_obj.risk_annotations = [
                {"phrase": "Bye", "offset": 7, "risk_level": "low", "risk_type": "ambiguity",
                 "explanation": "", "status": "accepted", "accepted_suggestion": "Goodbye."}
            ]
            _flag(res_obj, "risk_annotations")
            await db.commit()

            scorer_mod.bailian_client = FakeClient(_p(10, 10, 10, 10))
            res2 = await c.post(f"/api/jobs/{job_id}/acceptance-score/delta",
                                json={"lang": "en", "risk_index": 0})
            assert res2.status_code == 200
            # s1 re-scored 80→40; s0 stays 80; accepted risk → no penalty; mean(80,40)=60
            assert res2.json()["total_score"] == 60

            # verify new decision_log entry with trigger=sentence_replace + risk_index
            logs2 = (await db.execute(
                select(DecisionLog).where(DecisionLog.result_id == result_id,
                                          DecisionLog.stage == "acceptance")
            )).scalars().all()
            assert len(logs2) == 2
            delta_log = next(l for l in logs2 if l.metadata_.get("trigger") == "sentence_replace")
            assert delta_log.metadata_.get("risk_index") == 0
    finally:
        scorer_mod.bailian_client = orig
        app.dependency_overrides.clear()
