"""把 LLM 识别的风险短语映射到现有 risk_annotation，不产第二套高亮。"""

from app.schemas.acceptance import SentenceScore
from app.services.acceptance_segmenter import Sentence

_SEVERITY = {"high": 0, "medium": 1, "low": 2}


def map_risk_phrases(
    sentence_scores: list[SentenceScore],
    sentence_index: dict[str, Sentence],
    risk_annotations: list[dict],
) -> dict:
    """对齐 LLM 风险短语到现有标注。

    - 命中现有标注 → mapped_indices（引用其下标，不新增高亮）
    - 未命中 → unmapped_phrases（仅进 rationale 文字）
    - top3_risk_indices：未解决（open）的标注按严重度排序取前 3（accepted/dismissed 均已解决，不入选）
    """
    mapped_indices: set[int] = set()
    unmapped: list[str] = []

    for ss in sentence_scores:
        sent = sentence_index.get(ss.sentence_id)
        if sent is None:
            continue
        for (s_start, s_end) in ss.risk_phrase_offsets:
            full_start = sent.char_offset + s_start
            full_end = sent.char_offset + s_end
            phrase = sent.text[s_start:s_end] if 0 <= s_start <= s_end <= len(sent.text) else ""
            hit = _find_overlapping(risk_annotations, full_start, full_end)
            if hit is not None:
                mapped_indices.add(hit)
            elif phrase:
                unmapped.append(phrase)

    top3 = _top3(risk_annotations)
    return {
        "mapped_indices": sorted(mapped_indices),
        "unmapped_phrases": unmapped,
        "top3_risk_indices": top3,
    }


def _find_overlapping(anns: list[dict], start: int, end: int) -> int | None:
    """返回与 [start,end] 区间有重叠的标注下标，取覆盖度最高者。"""
    best_idx = None
    best_overlap = 0
    for i, ann in enumerate(anns):
        a_off = ann.get("offset", -1)
        if a_off < 0:
            continue
        a_phrase = ann.get("phrase", "")
        a_end = a_off + len(a_phrase)
        overlap = max(0, min(end, a_end) - max(start, a_off))
        if overlap > best_overlap:
            best_overlap = overlap
            best_idx = i
    return best_idx


def _top3(anns: list[dict]) -> list[int]:
    open_anns = [
        (i, ann) for i, ann in enumerate(anns)
        if ann.get("status", "open") == "open"
    ]
    open_anns.sort(key=lambda x: _SEVERITY.get(x[1].get("risk_level", "low"), 3))
    return [i for i, _ in open_anns[:3]]
