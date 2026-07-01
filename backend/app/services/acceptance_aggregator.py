"""句级评分聚合为全文评分。纯计算，无 LLM、无 IO。"""

from app.schemas.acceptance import SentenceScore

_RISK_PENALTY_PER_OPEN = 2
_RISK_PENALTY_CAP = 20
_DIM_KEYS = ("audience", "cultural", "naturalness", "risk")


def aggregate(
    sentence_scores: list[SentenceScore],
    risk_annotations: list[dict],
) -> dict:
    """句级 → 全文。失败句按非失败句维度均值填补，confidence 取最低。"""
    ok = [s for s in sentence_scores if not s.failed]
    if not ok:
        return {"total_score": -1, "dimensions": {k: 0.0 for k in _DIM_KEYS}, "confidence": 0.0}

    # 失败句填补：用非失败句的维度均值
    mean_dims = {
        k: sum(getattr(s.dimensions, k) for s in ok) / len(ok)
        for k in _DIM_KEYS
    }
    filled_scores: list[float] = []
    for s in sentence_scores:
        if s.failed:
            filled_scores.append(sum(mean_dims.values()))
        else:
            filled_scores.append(s.score)

    mean_score = sum(filled_scores) / len(filled_scores)

    open_risk_count = sum(
        1 for a in risk_annotations if a.get("status", "open") == "open"
    )
    penalty = min(open_risk_count * _RISK_PENALTY_PER_OPEN, _RISK_PENALTY_CAP)

    total = max(0, min(100, int(round(mean_score - penalty))))
    confidence = min(s.confidence for s in sentence_scores)
    return {
        "total_score": total,
        "dimensions": mean_dims,
        "confidence": confidence,
    }
