import uuid
import pytest
from app.models.job import TranslationJob, TranslationResult
from app.models.user import User


@pytest.mark.asyncio
async def test_translation_result_has_new_acceptance_fields(db):
    user = User(id=uuid.uuid4(), username=f"acc_{uuid.uuid4().hex[:8]}", hashed_password="x")
    db.add(user)
    await db.commit()
    job = TranslationJob(
        user_id=user.id, source_text="t", genre="political",
        strategy="semantic_equivalence", target_languages=["en"],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    result = TranslationResult(job_id=job.id, language="en", translated_text="Hello.")
    db.add(result)
    await db.commit()
    await db.refresh(result)

    # New fields exist and default correctly
    assert result.acceptance_confidence is None
    assert result.acceptance_dimensions is None
    assert result.acceptance_sentence_scores is None
    # Existing fields still present
    assert result.acceptance_score == -1
    assert result.audience_baseline is None
