import pytest
from pydantic import ValidationError
from app.schemas.acceptance import DimensionScores, SentenceScore, AcceptanceResult


def test_dimension_scores_clamps_range():
    d = DimensionScores(audience=10, cultural=20, naturalness=15, risk=25)
    assert d.audience == 10
    assert d.risk == 25


def test_dimension_scores_rejects_over_25():
    with pytest.raises(ValidationError):
        DimensionScores(audience=30, cultural=10, naturalness=10, risk=10)


def test_sentence_score_total_derived():
    s = SentenceScore(
        sentence_id="s0",
        dimensions=DimensionScores(audience=25, cultural=25, naturalness=25, risk=25),
        confidence=0.9,
        risk_phrase_offsets=[(0, 5)],
        affects_neighbors=False,
        rationale="ok",
    )
    assert s.score == 100  # derived = sum of dimensions


def test_sentence_score_failed_uses_minus_one():
    s = SentenceScore(
        sentence_id="s1",
        dimensions=DimensionScores(audience=0, cultural=0, naturalness=0, risk=0),
        confidence=0.0,
        risk_phrase_offsets=[],
        affects_neighbors=False,
        rationale="该句评分失败：timeout",
        failed=True,
    )
    assert s.score == -1


def test_acceptance_result_top3_optional():
    r = AcceptanceResult(
        total_score=72,
        dimensions=DimensionScores(audience=20, cultural=18, naturalness=17, risk=17),
        confidence=0.8,
        top3_risk_indices=[0, 2, 1],
        sentence_scores=[],
        audience_baseline="policy_media",
    )
    assert r.total_score == 72
    assert r.audience_baseline == "policy_media"