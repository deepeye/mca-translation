# backend/tests/test_acceptance_aggregator.py
from app.schemas.acceptance import DimensionScores, SentenceScore
from app.services.acceptance_aggregator import aggregate


def _ss(sid, dims, conf, failed=False):
    return SentenceScore(
        sentence_id=sid,
        dimensions=dims,
        confidence=conf,
        failed=failed,
    )


def test_aggregate_normal():
    scores = [
        _ss("s0", DimensionScores(audience=20, cultural=20, naturalness=20, risk=20), 0.9),  # score 80
        _ss("s1", DimensionScores(audience=10, cultural=10, naturalness=10, risk=10), 0.8),  # score 40
    ]
    r = aggregate(scores, [])
    # mean = 60, no risk penalty
    assert r["total_score"] == 60
    assert r["dimensions"]["audience"] == 15
    assert r["confidence"] == 0.8


def test_aggregate_risk_penalty():
    scores = [_ss("s0", DimensionScores(audience=25, cultural=25, naturalness=25, risk=25), 0.9)]  # score 100
    anns = [
        {"status": "open"}, {"status": "open"}, {"status": "open"},
    ]  # -2 * 3 = -6
    r = aggregate(scores, anns)
    assert r["total_score"] == 94  # 100 - 6


def test_aggregate_risk_penalty_capped():
    scores = [_ss("s0", DimensionScores(audience=25, cultural=25, naturalness=25, risk=25), 0.9)]
    anns = [{"status": "open"}] * 20  # -40 -> cap -20
    r = aggregate(scores, anns)
    assert r["total_score"] == 80  # 100 - 20


def test_aggregate_dismissed_not_penalized():
    scores = [_ss("s0", DimensionScores(audience=25, cultural=25, naturalness=25, risk=25), 0.9)]
    anns = [{"status": "dismissed"}, {"status": "open"}]  # only -2
    r = aggregate(scores, anns)
    assert r["total_score"] == 98


def test_aggregate_failed_sentence_filled_by_mean():
    scores = [
        _ss("s0", DimensionScores(audience=20, cultural=20, naturalness=20, risk=20), 0.9),  # 80
        _ss("s1", DimensionScores(audience=0, cultural=0, naturalness=0, risk=0), 0.0, failed=True),
    ]
    r = aggregate(scores, [])
    # failed filled by mean of non-failed dims -> 20,20,20,20 = 80; mean(80,80)=80
    assert r["total_score"] == 80
    assert r["confidence"] == 0.0  # min(0.9, 0.0)


def test_aggregate_all_failed():
    scores = [_ss("s0", DimensionScores(audience=0, cultural=0, naturalness=0, risk=0), 0.0, failed=True)]
    r = aggregate(scores, [])
    assert r["total_score"] == -1
    assert r["confidence"] == 0.0