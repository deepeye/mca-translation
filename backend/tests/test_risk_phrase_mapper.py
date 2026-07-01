from app.services.acceptance_segmenter import Sentence
from app.schemas.acceptance import DimensionScores, SentenceScore
from app.services.risk_phrase_mapper import map_risk_phrases


def _ss(sid, offsets):
    return SentenceScore(
        sentence_id=sid,
        dimensions=DimensionScores(audience=10, cultural=10, naturalness=10, risk=10),
        confidence=0.9,
        risk_phrase_offsets=offsets,
        affects_neighbors=False,
        rationale="",
    )


def test_map_hits_existing_annotation():
    # sentence s0 at offset 0, LLM phrase [0,5] => full-text [0,5]
    sents = {"s0": Sentence("s0", "Hello world.", 0, 12)}
    scores = [_ss("s0", [(0, 5)])]
    anns = [{"phrase": "Hello", "offset": 0, "risk_level": "high", "status": "open"}]
    r = map_risk_phrases(scores, sents, anns)
    assert 0 in r["mapped_indices"]
    assert r["unmapped_phrases"] == []
    assert r["top3_risk_indices"] == [0]


def test_map_unmatched_goes_to_rationale():
    sents = {"s0": Sentence("s0", "Hello world.", 0, 12)}
    scores = [_ss("s0", [(6, 11)])]  # "world" — no annotation
    anns = [{"phrase": "Hello", "offset": 0, "risk_level": "high", "status": "open"}]
    r = map_risk_phrases(scores, sents, anns)
    assert r["mapped_indices"] == []
    assert r["unmapped_phrases"] == ["world"]


def test_top3_sorts_by_severity_excludes_dismissed():
    # accepted（已替换）与 dismissed（用户保留）均视为已解决，不进 top3；仅 open 入选。
    anns = [
        {"phrase": "a", "offset": 0, "risk_level": "low", "status": "open"},
        {"phrase": "b", "offset": 1, "risk_level": "high", "status": "open"},
        {"phrase": "c", "offset": 2, "risk_level": "medium", "status": "open"},
        {"phrase": "d", "offset": 3, "risk_level": "high", "status": "dismissed"},  # excluded
        {"phrase": "e", "offset": 4, "risk_level": "high", "status": "accepted"},  # excluded
    ]
    r = map_risk_phrases([], {}, anns)
    # high(b) > medium(c) > low(a); d/e excluded
    assert r["top3_risk_indices"] == [1, 2, 0]


def test_no_annotations_returns_empty():
    r = map_risk_phrases([], {}, [])
    assert r == {"mapped_indices": [], "unmapped_phrases": [], "top3_risk_indices": []}
