"""验证 cultural 相关 schema 的字段和默认值。"""
import pytest
from pydantic import ValidationError

from app.schemas.job import (
    CreateJobRequest,
    CulturalLoadedTerm,
    CulturalPreprocessResult,
    TranslationResultResponse,
)


def test_cultural_loaded_term_accepts_valid_payload():
    term = CulturalLoadedTerm(
        term="共同富裕",
        culture_gap="high",
        adaptation_strategy="explanatory",
        suggested_rendering="a policy initiative aimed at balanced wealth distribution",
        reason="lacks context for Western audiences",
    )
    assert term.adaptation_strategy == "explanatory"


def test_cultural_loaded_term_rejects_unknown_strategy():
    with pytest.raises(ValidationError):
        CulturalLoadedTerm(
            term="x",
            culture_gap="low",
            adaptation_strategy="invented",
            suggested_rendering="x",
            reason="x",
        )


def test_cultural_preprocess_result_defaults_to_empty_lists():
    result = CulturalPreprocessResult()
    assert result.culture_loaded_terms == []
    assert result.cultural_notes == []
    assert result.taboo_warnings == []


def test_create_job_request_cultural_fields_optional():
    req = CreateJobRequest(
        source_text="hello",
        genre="political",
        target_languages=["en-GB"],
    )
    assert req.cultural_sphere is None
    assert req.audience_type is None


def test_create_job_request_accepts_cultural_fields():
    req = CreateJobRequest(
        source_text="hello",
        genre="political",
        target_languages=["en-GB"],
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert req.cultural_sphere == "western_english"
    assert req.audience_type == "general_public"


def test_translation_result_response_cultural_adaptation_optional():
    import uuid
    from datetime import datetime, timezone

    resp = TranslationResultResponse(
        id=uuid.uuid4(),
        language="en-GB",
        status="completed",
        translated_text="x",
        acceptance_score=-1,
        risk_annotations=None,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.cultural_adaptation is None
