import pytest
from pydantic import ValidationError

from app.schemas.narrative_reframe import (
    NarrativeReframeAnalysis,
    NarrativeRecommendedItem,
    NarrativePreviewRequest,
)


def _analysis(confidence=0.8, reason_label="audience_habit"):
    return NarrativeReframeAnalysis(
        source_outline=[{"id": "s1", "order": 1, "summary": "背景", "text_span": "背景段"}],
        current_translation_outline=[{"id": "t1", "order": 1, "summary": "Background", "text_span": "Background"}],
        recommended_outline=[{
            "id": "r1", "target_order": 1, "source_ref_ids": ["t1"],
            "summary": "Lead with impact", "reason_label": reason_label,
            "reason": "目标受众先看影响", "expected_effect": "更快进入主题",
        }],
        overall_rationale="当前结构背景先行。",
        confidence=confidence,
    )


def test_analysis_accepts_valid_payload():
    assert _analysis().recommended_outline[0].reason_label == "audience_habit"


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_between_zero_and_one(confidence):
    with pytest.raises(ValidationError):
        _analysis(confidence=confidence)


def test_reason_label_must_be_known_literal():
    with pytest.raises(ValidationError):
        _analysis(reason_label="other")


def test_preview_mode_only_supports_light_cohesion():
    NarrativePreviewRequest(lang="en", analysis=_analysis(), text_hash="abc", mode="light_cohesion")
    with pytest.raises(ValidationError):
        NarrativePreviewRequest(lang="en", analysis=_analysis(), text_hash="abc", mode="full_rewrite")
