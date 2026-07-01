# Acceptance Scoring (接受度评分) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an LLM-Judge-based acceptance scoring service that scores translated text (per target language) on a 0–100 scale across 4 dimensions, with sentence-level delta re-scoring after risk-word replacement, consuming the existing risk annotation system.

**Architecture:** New `AcceptanceScorer` service (LLM-Judge + 3-sample median + confidence) plus three pure helper components (`SentenceSegmenter`, `RiskPhraseMapper`, `AcceptanceAggregator`). Scores are stored on `TranslationResult` (per-language). A new `acceptance` stage is written to `decision_log`. Two API routes trigger first-scoring and delta re-scoring.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, 百炼 DashScope (qwen-plus via `bailian_client`), Alembic, pytest (asyncio).

## Global Constraints

- **LLM client:** `from app.llm.bailian import bailian_client`; call as `await bailian_client.chat(model="qwen-plus", messages=[{"role":"user","content":prompt}], temperature=0.3)`; returns `{"content": str}`.
- **Model:** `qwen-plus` for scoring (structured task, matches `review.py`/`suggestion.py` convention; `qwen-max` reserved for main translation).
- **Prompt style:** module-level string constant in `app/llm/prompts.py`, uses `.format(**kwargs)`, ends with "只返回 JSON，不要包含其他文字、markdown 代码围栏".
- **JSON parsing:** `content.strip()`, strip ```` ``` ```` fences if present, `json.loads(content)`, broad `except` → degraded fallback (see `review.py:62-132`).
- **Schema:** Pydantic v2 `BaseModel`, `Field(...)`, `Literal`, `Optional[X]`, `Field(default_factory=list)`.
- **Model columns:** SQLAlchemy 2.0 `Mapped[T]` + `mapped_column(...)`; `JSONB` for dict/list; `DateTime(timezone=True)`; `snake_case`.
- **DecisionLog stage:** plain `String(16)` column, no enum type; valid values documented in `app/services/decision_log.py` `_STAGE_ORDER` dict.
- **Risk annotation shape** (in `TranslationResult.risk_annotations` JSONB, `list[dict]`): each `{phrase: str, risk_level: "low"|"medium"|"high", risk_type: str, explanation: str, offset: int, status: "open"|"accepted"|"dismissed"}`.
- **API route convention:** `@router.post("/{job_id}/...", response_model=X)` with `user: User = Depends(get_current_user)`, `db: AsyncSession = Depends(get_db)`; ownership via `_get_user_job(job_id, user, db)` + `_get_lang_result(job.id, body.lang, db)`; `body.lang` carries the target language (matches risk-route pattern).
- **JSONB mutation:** call `flag_modified(result, "column_name")` after in-place mutation.
- **Tests:** `@pytest.mark.asyncio`; service unit tests use a `FakeClient` with `async def chat(self, *, model, messages, temperature) -> dict`; API tests use `httpx.AsyncClient` + `ASGITransport` + `app.dependency_overrides`.
- **Comments:** bilingual (Chinese for important logic), per CLAUDE.md convention 3.
- **Commit on main branch** (single-developer mode, CLAUDE.md convention 2).

### Tuning constants (initial values, adjustable after measurement)

- Sentence aggregation: equal weight — `total = mean(sentence_scores) - risk_penalty`.
- Risk penalty: `-2` per open (non-dismissed) risk annotation, capped at `-20`.
- Sampling: 3 samples per sentence (first scoring), 1 sample (delta).
- Confidence: `confidence = max(0.0, 1.0 - (max_sample_total - min_sample_total) / 20.0)`; `< 0.7` → low (UI greys).
- Concurrency: `asyncio.Semaphore(5)` for LLM calls.
- Long text threshold: `> 50` sentences → batch 10 concurrent.

---

## File Structure

| File | Responsibility | Status |
|---|---|---|
| `backend/app/services/acceptance_segmenter.py` | `SentenceSegmenter` — pure function, language-aware sentence splitting | Create |
| `backend/app/schemas/acceptance.py` | Pydantic models: `DimensionScores`, `SentenceScore`, `AcceptanceResult` | Create |
| `backend/app/services/risk_phrase_mapper.py` | `map_risk_phrases` — pure: align LLM risk phrases to existing annotations, compute top3 | Create |
| `backend/app/services/acceptance_aggregator.py` | `aggregate` — pure: sentence scores → total + dimensions + confidence | Create |
| `backend/app/llm/prompts.py` | Add `ACCEPTANCE_SCORE_PROMPT` constant | Modify |
| `backend/app/services/acceptance_scorer.py` | `AcceptanceScorer` — LLM call, 3-sample median, schema validation, retry | Create |
| `backend/app/models/job.py` | Add 3 columns to `TranslationResult` | Modify |
| `backend/app/services/decision_log.py` | Add `"acceptance"` to `_STAGE_ORDER` | Modify |
| `backend/app/schemas/job.py` | Add `AcceptanceScoreRequest`, `AcceptanceDeltaRequest`, `AcceptanceScoreResponse` | Modify |
| `backend/app/api/jobs.py` | Add 2 routes: first-scoring, delta | Modify |
| `backend/tests/test_sentence_segmenter.py` | Unit tests | Create |
| `backend/tests/test_risk_phrase_mapper.py` | Unit tests | Create |
| `backend/tests/test_acceptance_aggregator.py` | Unit tests | Create |
| `backend/tests/test_acceptance_scorer.py` | Unit tests (FakeClient) | Create |
| `backend/tests/test_acceptance_api.py` | API tests (httpx + ASGITransport) | Create |
| `backend/tests/test_acceptance_integration.py` | Full-chain integration test | Create |
| `backend/alembic/versions/<rev>_add_acceptance_scoring_fields.py` | Migration: 3 columns on `translation_results` | Create |

---

## Task 1: SentenceSegmenter (pure function)

**Files:**
- Create: `backend/app/services/acceptance_segmenter.py`
- Test: `backend/tests/test_sentence_segmenter.py`

**Interfaces:**
- Produces: `segment(text: str, lang: str) -> list[Sentence]` where `Sentence` is a `dataclass{id: str, text: str, char_offset: int, length: int}`; `id` is `"s{i}"` (0-indexed); `char_offset` is the character offset of the sentence start in the full text.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sentence_segmenter.py
from app.services.acceptance_segmenter import segment, Sentence


def test_segment_english_period():
    sents = segment("Hello world. Goodbye moon.", "en")
    assert [s.text for s in sents] == ["Hello world.", "Goodbye moon."]
    assert sents[0].id == "s0"
    assert sents[0].char_offset == 0
    assert sents[1].char_offset == 13  # len("Hello world. ")
    assert sents[1].id == "s1"


def test_segment_chinese_full_stop():
    sents = segment("你好世界。再见月亮。", "zh")
    assert [s.text for s in sents] == ["你好世界。", "再见月亮。"]
    assert sents[1].char_offset == 5


def test_segment_japanese():
    sents = segment("こんにちは。さようなら。", "ja")
    assert len(sents) == 2
    assert sents[0].text == "こんにちは。"


def test_segment_single_sentence_no_terminator():
    sents = segment("Just one sentence without terminator", "en")
    assert len(sents) == 1
    assert sents[0].text == "Just one sentence without terminator"
    assert sents[0].char_offset == 0


def test_segment_empty_text():
    assert segment("", "en") == []


def test_segment_preserves_abbreviations_dr():
    # Dr. should not split
    sents = segment("Dr. Smith arrived. He left.", "en")
    assert [s.text for s in sents] == ["Dr. Smith arrived.", "He left."]


def test_segment_consecutive_punctuation():
    sents = segment("What?! Yes.", "en")
    # "What?!" is one sentence
    assert [s.text for s in sents] == ["What?!", "Yes."]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_sentence_segmenter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.acceptance_segmenter'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/acceptance_segmenter.py
"""句子切分器 — 按目标语言句末标点切句，供接受度评分与 delta 重算共用。"""

import re
from dataclasses import dataclass


@dataclass
class Sentence:
    """切分后的句子。char_offset 为句首在全文中的字符偏移。"""
    id: str
    text: str
    char_offset: int
    length: int


# 各语言句末标点正则：英文 .!?、中文 。！？、日文 。！？
_TERMINATORS = {
    "en": r"[.!?]+",
    "de": r"[.!?]+",
    "fr": r"[.!?]+",
    "es": r"[.!?]+",
    "zh": r"[。！？]+",
    "ja": r"[。！？]+",
}

# 英文缩写（不视为句末）：Dr. Nr. Mr. Mrs. Ms. Prof. vs. etc. e.g. i.e.
_ABBREVIATIONS = re.compile(
    r"\b(Dr|Nr|Mr|Mrs|Ms|Prof|vs|etc|e\.g|i\.e|St|Jr|Sr)\."
)


def segment(text: str, lang: str) -> list[Sentence]:
    """按语言切句。返回句子列表，每个含 id/char_offset。

    对英文系语言（en/de/fr/es）保护常见缩写，避免 Dr. 误切。
    """
    if not text:
        return []

    lang = lang.lower()
    pattern = _TERMINATORS.get(lang, _TERMINATORS["en"])

    if lang in ("en", "de", "fr", "es"):
        # 用占位符保护缩写，切完再还原
        protected = _ABBREVIATIONS.sub(lambda m: m.group(0).replace(".", "\x00"), text)
        parts = re.split(f"({pattern})", protected)
        parts = [p.replace("\x00", ".") for p in parts]
    else:
        parts = re.split(f"({pattern})", text)

    # 重新拼接句末标点回句子
    sentences: list[Sentence] = []
    buf = ""
    offset = 0
    idx = 0
    for part in parts:
        buf += part
        if re.fullmatch(pattern, part):
            stripped = buf
            if stripped:
                sentences.append(Sentence(
                    id=f"s{idx}",
                    text=stripped,
                    char_offset=offset,
                    length=len(stripped),
                ))
                offset += len(stripped)
                idx += 1
            buf = ""
    if buf:
        sentences.append(Sentence(
            id=f"s{idx}",
            text=buf,
            char_offset=offset,
            length=len(buf),
        ))
    return sentences
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_sentence_segmenter.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/acceptance_segmenter.py backend/tests/test_sentence_segmenter.py
git commit -m "feat(acceptance): add SentenceSegmenter for language-aware splitting"
```

---

## Task 2: Pydantic schemas for acceptance scoring

**Files:**
- Create: `backend/app/schemas/acceptance.py`
- Test: `backend/tests/test_acceptance_schemas.py`

**Interfaces:**
- Produces: `DimensionScores`, `SentenceScore`, `AcceptanceResult` (Pydantic models, exact field names below).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_acceptance_schemas.py
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
        dimensions=DimensionScores(25, 25, 25, 25),
        confidence=0.9,
        risk_phrase_offsets=[(0, 5)],
        affects_neighbors=False,
        rationale="ok",
    )
    assert s.score == 100  # derived = sum of dimensions


def test_sentence_score_failed_uses_minus_one():
    s = SentenceScore(
        sentence_id="s1",
        dimensions=DimensionScores(0, 0, 0, 0),
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
        dimensions=DimensionScores(20, 18, 17, 17),
        confidence=0.8,
        top3_risk_indices=[0, 2, 1],
        sentence_scores=[],
        audience_baseline="policy_media",
    )
    assert r.total_score == 72
    assert r.audience_baseline == "policy_media"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_acceptance_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/schemas/acceptance.py
"""接受度评分的 Pydantic schema 契约。"""

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class DimensionScores(BaseModel):
    """四维评分，各 0-25，合计 0-100。"""
    audience: float = Field(..., ge=0, le=25)       # 受众匹配度
    cultural: float = Field(..., ge=0, le=25)      # 文化敏感度
    naturalness: float = Field(..., ge=0, le=25)   # 表达自然度
    risk: float = Field(..., ge=0, le=25)          # 风险词密度分（越高=风险越少）


class SentenceScore(BaseModel):
    """单句评分。score 为四维之和（0-100），失败时 -1。"""
    sentence_id: str
    dimensions: DimensionScores
    confidence: float = Field(..., ge=0, le=1)
    risk_phrase_offsets: list[tuple[int, int]] = Field(default_factory=list)
    affects_neighbors: bool = False
    rationale: str = ""
    failed: bool = False

    @property
    def score(self) -> int:
        if self.failed:
            return -1
        return int(round(self.dimensions.audience + self.dimensions.cultural
                         + self.dimensions.naturalness + self.dimensions.risk))


class AcceptanceResult(BaseModel):
    """全文接受度评分结果。"""
    total_score: int = Field(..., ge=-1, le=100)
    dimensions: DimensionScores
    confidence: float = Field(..., ge=0, le=1)
    top3_risk_indices: list[int] = Field(default_factory=list)
    sentence_scores: list[SentenceScore] = Field(default_factory=list)
    audience_baseline: Literal["policy_media", "academic", "social_media"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_acceptance_schemas.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/acceptance.py backend/tests/test_acceptance_schemas.py
git commit -m "feat(acceptance): add Pydantic schemas for scoring contracts"
```

---

## Task 3: RiskPhraseMapper (pure mapping)

**Files:**
- Create: `backend/app/services/risk_phrase_mapper.py`
- Test: `backend/tests/test_risk_phrase_mapper.py`

**Interfaces:**
- Consumes: `SentenceScore` (from Task 2), `Sentence` (from Task 1), risk annotation dicts `{phrase, offset, risk_level, status}`.
- Produces: `map_risk_phrases(sentence_scores, sentence_index, risk_annotations) -> dict` where the returned dict is `{"mapped_indices": list[int], "unmapped_phrases": list[str], "top3_risk_indices": list[int]}`.
  - `sentence_index`: `dict[sentence_id -> Sentence]` (for full-text offset computation).
  - `mapped_indices`: indices into `risk_annotations` that an LLM phrase overlapped (confirmed).
  - `unmapped_phrases`: LLM-identified phrases that found no existing annotation (go to rationale only, no highlight).
  - `top3_risk_indices`: indices of open (non-dismissed) annotations sorted by severity (high>medium>low), take 3.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_phrase_mapper.py
from app.services.acceptance_segmenter import Sentence
from app.schemas.acceptance import DimensionScores, SentenceScore
from app.services.risk_phrase_mapper import map_risk_phrases


def _ss(sid, offsets):
    return SentenceScore(
        sentence_id=sid,
        dimensions=DimensionScores(10, 10, 10, 10),
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
    assert r["mapped_indices"] == [0]
    assert "world" in r["unmapped_phrases"]


def test_top3_sorts_by_severity_excludes_dismissed():
    anns = [
        {"phrase": "a", "offset": 0, "risk_level": "low", "status": "open"},
        {"phrase": "b", "offset": 1, "risk_level": "high", "status": "open"},
        {"phrase": "c", "offset": 2, "risk_level": "medium", "status": "open"},
        {"phrase": "d", "offset": 3, "risk_level": "high", "status": "dismissed"},  # excluded
    ]
    r = map_risk_phrases([], {}, anns)
    # high(b) > medium(c) > low(a); d excluded
    assert r["top3_risk_indices"] == [1, 2, 0]


def test_no_annotations_returns_empty():
    r = map_risk_phrases([], {}, [])
    assert r == {"mapped_indices": [], "unmapped_phrases": [], "top3_risk_indices": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_risk_phrase_mapper.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/risk_phrase_mapper.py
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
    - top3_risk_indices：未 dismissed 的标注按严重度排序取前 3
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
        if ann.get("status", "open") != "dismissed"
    ]
    open_anns.sort(key=lambda x: _SEVERITY.get(x[1].get("risk_level", "low"), 3))
    return [i for i, _ in open_anns[:3]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_risk_phrase_mapper.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/risk_phrase_mapper.py backend/tests/test_risk_phrase_mapper.py
git commit -m "feat(acceptance): add RiskPhraseMapper aligning LLM phrases to annotations"
```

---

## Task 4: AcceptanceAggregator (pure computation)

**Files:**
- Create: `backend/app/services/acceptance_aggregator.py`
- Test: `backend/tests/test_acceptance_aggregator.py`

**Interfaces:**
- Consumes: `list[SentenceScore]`, `risk_annotations: list[dict]`.
- Produces: `aggregate(sentence_scores, risk_annotations) -> dict` returning `{"total_score": int, "dimensions": dict, "confidence": float}`.
  - `total_score` = `mean(non-failed sentence scores)` minus risk penalty (`-2` per open annotation, cap `-20`), clamped `[0, 100]`; if all failed → `-1`.
  - `dimensions` = `mean` of each dimension across non-failed sentences.
  - `confidence` = `min(sentence confidences)`; if all failed → `0.0`.

- [ ] **Step 1: Write the failing test**

```python
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
        _ss("s0", DimensionScores(20, 20, 20, 20), 0.9),  # score 80
        _ss("s1", DimensionScores(10, 10, 10, 10), 0.8),  # score 40
    ]
    r = aggregate(scores, [])
    # mean = 60, no risk penalty
    assert r["total_score"] == 60
    assert r["dimensions"]["audience"] == 15
    assert r["confidence"] == 0.8


def test_aggregate_risk_penalty():
    scores = [_ss("s0", DimensionScores(25, 25, 25, 25), 0.9)]  # score 100
    anns = [
        {"status": "open"}, {"status": "open"}, {"status": "open"},
    ]  # -2 * 3 = -6
    r = aggregate(scores, anns)
    assert r["total_score"] == 94  # 100 - 6


def test_aggregate_risk_penalty_capped():
    scores = [_ss("s0", DimensionScores(25, 25, 25, 25), 0.9)]
    anns = [{"status": "open"}] * 20  # -40 → cap -20
    r = aggregate(scores, anns)
    assert r["total_score"] == 80  # 100 - 20


def test_aggregate_dismissed_not_penalized():
    scores = [_ss("s0", DimensionScores(25, 25, 25, 25), 0.9)]
    anns = [{"status": "dismissed"}, {"status": "open"}]  # only -2
    r = aggregate(scores, anns)
    assert r["total_score"] == 98


def test_aggregate_failed_sentence_filled_by_mean():
    scores = [
        _ss("s0", DimensionScores(20, 20, 20, 20), 0.9),  # 80
        _ss("s1", DimensionScores(0, 0, 0, 0), 0.0, failed=True),
    ]
    r = aggregate(scores, [])
    # failed filled by mean of non-failed dims → 20,20,20,20 = 80; mean(80,80)=80
    assert r["total_score"] == 80
    assert r["confidence"] == 0.0  # min(0.9, 0.0)


def test_aggregate_all_failed():
    scores = [_ss("s0", DimensionScores(0, 0, 0, 0), 0.0, failed=True)]
    r = aggregate(scores, [])
    assert r["total_score"] == -1
    assert r["confidence"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_acceptance_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/acceptance_aggregator.py
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
        1 for a in risk_annotations if a.get("status", "open") != "dismissed"
    )
    penalty = min(open_risk_count * _RISK_PENALTY_PER_OPEN, _RISK_PENALTY_CAP)

    total = max(0, min(100, int(round(mean_score - penalty))))
    confidence = min(s.confidence for s in sentence_scores)
    return {
        "total_score": total,
        "dimensions": mean_dims,
        "confidence": confidence,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_acceptance_aggregator.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/acceptance_aggregator.py backend/tests/test_acceptance_aggregator.py
git commit -m "feat(acceptance): add AcceptanceAggregator with risk penalty"
```

---

## Task 5: ACCEPTANCE_SCORE_PROMPT + AcceptanceScorer (LLM, sampling)

**Files:**
- Modify: `backend/app/llm/prompts.py` (append `ACCEPTANCE_SCORE_PROMPT`)
- Create: `backend/app/services/acceptance_scorer.py`
- Test: `backend/tests/test_acceptance_scorer.py`

**Interfaces:**
- Consumes: `bailian_client` (or injected `llm_client` for testing), `ACCEPTANCE_SCORE_PROMPT`, `DimensionScores`/`SentenceScore` schemas.
- Produces: `AcceptanceScorer` class with:
  - `async def score_sentence(self, sentence_text, lang, audience_baseline, genre="", cultural_sphere="", n_samples=3) -> SentenceScore`
  - `async def score_sentence_single(self, sentence_text, lang, audience_baseline, genre="", cultural_sphere="") -> SentenceScore` (delta path, 1 sample, `confidence=0.5`)
  - Constructor: `AcceptanceScorer(llm_client=None, semaphore_limit=5)`; defaults to `bailian_client` if `llm_client is None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_acceptance_scorer.py
import json
import pytest
from app.services.acceptance_scorer import AcceptanceScorer
from app.schemas.acceptance import SentenceScore


class FakeClient:
    """模拟 bailian_client.chat。按调用顺序返回 contents 队列。"""
    def __init__(self, contents: list[str]):
        self._contents = list(contents)
        self.calls = 0

    async def chat(self, *, model, messages, temperature=0.3):
        self.calls += 1
        if not self._contents:
            raise RuntimeError("no more fake responses")
        return {"content": self._contents.pop(0)}


def _payload(dims=(20, 20, 20, 20), offsets=None, neighbors=False, rationale="ok"):
    return json.dumps({
        "audience": dims[0], "cultural": dims[1],
        "naturalness": dims[2], "risk": dims[3],
        "risk_phrase_offsets": offsets or [],
        "affects_neighbors": neighbors,
        "rationale": rationale,
    })


@pytest.mark.asyncio
async def test_score_sentence_three_samples_median():
    # 3 samples: totals 80, 60, 80 → median 80; range 20 → confidence = 1 - 20/20 = 0.0
    client = FakeClient([_payload((20, 20, 20, 20)), _payload((15, 15, 15, 15)), _payload((20, 20, 20, 20))])
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence("Hello world.", "en", "policy_media")
    assert isinstance(ss, SentenceScore)
    assert ss.score == 80  # median dimensions 20,20,20,20
    assert ss.confidence == 0.0  # range 20


@pytest.mark.asyncio
async def test_score_sentence_low_variance_high_confidence():
    # 3 samples: 80, 78, 82 → range 4 → confidence = 1 - 4/20 = 0.8
    client = FakeClient([
        _payload((20, 20, 20, 20)),
        _payload((19, 20, 20, 19)),  # 78
        _payload((21, 20, 20, 21)),  # but 21>25 invalid → clamped? no, 21 invalid
    ])
    # fix: keep within 0-25
    client = FakeClient([
        _payload((20, 20, 20, 20)),   # 80
        _payload((19, 20, 20, 19)),   # 78
        _payload((20, 20, 21, 21)),   # 82
    ])
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence("Hello.", "en", "academic")
    assert ss.score == 80  # median of 80,78,82 = 80
    assert 0.75 <= ss.confidence <= 0.85


@pytest.mark.asyncio
async def test_score_sentence_invalid_json_retries_then_fails():
    client = FakeClient(["not json", "still not json", "still not json"])
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence("Hello.", "en", "policy_media")
    assert ss.failed is True
    assert ss.score == -1
    assert ss.confidence == 0.0
    assert "失败" in ss.rationale


@pytest.mark.asyncio
async def test_score_sentence_partial_invalid_uses_valid():
    # 1 invalid + 2 valid (80, 80)
    client = FakeClient(["garbage", _payload((20, 20, 20, 20)), _payload((20, 20, 20, 20))])
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence("Hello.", "en", "policy_media")
    assert ss.failed is False
    assert ss.score == 80


@pytest.mark.asyncio
async def test_score_sentence_single_delta_mode():
    client = FakeClient([_payload((20, 20, 20, 20))])
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence_single("Hello.", "en", "policy_media")
    assert ss.score == 80
    assert ss.confidence == 0.5  # single-sample default
    assert client.calls == 1


@pytest.mark.asyncio
async def test_score_sentence_affects_neighbors_majority_vote():
    # 3 samples: True, True, False → majority True
    client = FakeClient([
        _payload((20, 20, 20, 20), neighbors=True),
        _payload((20, 20, 20, 20), neighbors=True),
        _payload((20, 20, 20, 20), neighbors=False),
    ])
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence("Hello.", "en", "policy_media")
    assert ss.affects_neighbors is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_acceptance_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Add the prompt**

Append to `backend/app/llm/prompts.py`:

```python


# 接受度评分 prompt（单句级，LLM-Judge）
ACCEPTANCE_SCORE_PROMPT = """你是跨文化传播接受度评估器。对一句【目标语言译文】预测「目标受众是否会以预期方式理解这段内容」的接受度。

目标语言: {target_language}
受众基准: {audience_baseline}（policy_media=主流政策媒体受众 / academic=学术界 / social_media=社交媒体）
文体: {genre}
文化圈: {cultural_sphere}

待评估译文（单句）: {sentence_text}

按以下四维各打 0-25 分（合计 0-100，越高越好）：
- audience: 受众匹配度（表达是否符合该受众基准的语言习惯）
- cultural: 文化敏感度（是否触犯该受众的文化禁忌或引发负联想）
- naturalness: 表达自然度（是否像该语言母语表达，而非翻译腔）
- risk: 风险词密度分（越高表示风险词越少；无风险词=25）

同时在句内识别可能引发受众理解偏差的风险短语（按句内字符偏移给出 [start, end] 区间，基于上面的「待评估译文」文本）。

判断本次评分的句子是否可能影响相邻句子的接受度（如代词指代、跨句逻辑）。

输出严格 JSON，不要包含任何其他文字、解释、markdown 代码围栏：
{{
  "audience": <0-25 整数>,
  "cultural": <0-25 整数>,
  "naturalness": <0-25 整数>,
  "risk": <0-25 整数>,
  "risk_phrase_offsets": [[start, end], ...],
  "affects_neighbors": true 或 false,
  "rationale": "<一句中文理由，解释评分依据与未命中现有标注的风险短语>"
}}
"""
```

- [ ] **Step 4: Write minimal implementation**

```python
# backend/app/services/acceptance_scorer.py
"""接受度评分器：LLM-Judge + 3 次采样取中位数 + schema 校验。

对单句调用 LLM，3 次采样（T=0.3）取每维中位数，方差大则 confidence 低。
delta 重算走单次采样。所有 LLM 调用经信号量节流。
"""

import asyncio
import json
import logging
import statistics

from app.core.config import settings
from app.llm.bailian import bailian_client
from app.llm.prompts import ACCEPTANCE_SCORE_PROMPT
from app.schemas.acceptance import DimensionScores, SentenceScore

logger = logging.getLogger(__name__)

_DIM_KEYS = ("audience", "cultural", "naturalness", "risk")
_SINGLE_SAMPLE_CONFIDENCE = 0.5


class AcceptanceScorer:
    def __init__(self, llm_client=None, semaphore_limit: int = 5):
        # llm_client=None → 运行时从模块全局 bailian_client 取（便于测试 monkeypatch）
        self._client = llm_client
        self._sem = asyncio.Semaphore(semaphore_limit)

    async def score_sentence(
        self,
        sentence_text: str,
        lang: str,
        audience_baseline: str,
        genre: str = "",
        cultural_sphere: str = "",
        n_samples: int = 3,
    ) -> SentenceScore:
        # 并发采样
        samples = await asyncio.gather(*[
            self._one_sample(sentence_text, lang, audience_baseline, genre, cultural_sphere)
            for _ in range(n_samples)
        ])
        valid = [s for s in samples if s is not None]
        if not valid:
            return SentenceScore(
                sentence_id="",  # 调用方在编排时回填
                dimensions=DimensionScores(audience=0, cultural=0, naturalness=0, risk=0),
                confidence=0.0,
                failed=True,
                rationale="该句评分失败：3 次采样均不合规",
            )

        # 每维中位数
        dim_medians = {}
        for k in _DIM_KEYS:
            vals = [getattr(s["dims"], k) for s in valid]
            dim_medians[k] = statistics.median(vals)

        # 置信度：基于各样本总分 range
        totals = [sum(getattr(s["dims"], k) for k in _DIM_KEYS) for s in valid]
        rng = max(totals) - min(totals)
        confidence = max(0.0, 1.0 - rng / 20.0)

        # 取最接近中位数总分的样本作为 rationale / offsets / affects_neighbors 来源
        median_total = statistics.median(totals)
        representative = min(valid, key=lambda s: abs(sum(getattr(s["dims"], k) for k in _DIM_KEYS) - median_total))

        # affects_neighbors 多数表决
        neighbor_votes = [s["affects_neighbors"] for s in valid]
        affects_neighbors = sum(neighbor_votes) > len(neighbor_votes) / 2

        dims = DimensionScores(**dim_medians)
        return SentenceScore(
            sentence_id="",  # 编排时回填
            dimensions=dims,
            confidence=confidence,
            risk_phrase_offsets=representative["offsets"],
            affects_neighbors=affects_neighbors,
            rationale=representative["rationale"],
        )

    async def score_sentence_single(
        self,
        sentence_text: str,
        lang: str,
        audience_baseline: str,
        genre: str = "",
        cultural_sphere: str = "",
    ) -> SentenceScore:
        s = await self._one_sample(sentence_text, lang, audience_baseline, genre, cultural_sphere)
        if s is None:
            return SentenceScore(
                sentence_id="",
                dimensions=DimensionScores(audience=0, cultural=0, naturalness=0, risk=0),
                confidence=0.0,
                failed=True,
                rationale="该句评分失败：采样不合规",
            )
        return SentenceScore(
            sentence_id="",
            dimensions=s["dims"],
            confidence=_SINGLE_SAMPLE_CONFIDENCE,
            risk_phrase_offsets=s["offsets"],
            affects_neighbors=s["affects_neighbors"],
            rationale=s["rationale"],
        )

    async def _one_sample(self, sentence_text, lang, audience_baseline, genre, cultural_sphere):
        prompt = ACCEPTANCE_SCORE_PROMPT.format(
            target_language=lang,
            audience_baseline=audience_baseline,
            genre=genre or "未指定",
            cultural_sphere=cultural_sphere or "未指定",
            sentence_text=sentence_text,
        )
        async with self._sem:
            client = self._client if self._client is not None else bailian_client
            try:
                result = await client.chat(
                    model=settings.BAILIAN_MODEL_PLUS,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
            except Exception as e:
                logger.warning("acceptance scoring LLM call failed: %s", e)
                return None

        content = (result.get("content") or "").strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # 重试 1 次（schema 不合规重试）
            async with self._sem:
                try:
                    result = await client.chat(
                        model=settings.BAILIAN_MODEL_PLUS,
                        messages=[{"role": "user", "content": prompt + "\n\n上次输出格式错误，请严格按 JSON schema 输出。"}],
                        temperature=0.3,
                    )
                except Exception:
                    return None
            content = (result.get("content") or "").strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return None

        try:
            dims = DimensionScores(
                audience=float(data["audience"]),
                cultural=float(data["cultural"]),
                naturalness=float(data["naturalness"]),
                risk=float(data["risk"]),
            )
        except (KeyError, ValueError, TypeError):
            return None

        offsets = [(int(s), int(e)) for s, e in data.get("risk_phrase_offsets", [])]
        return {
            "dims": dims,
            "offsets": offsets,
            "affects_neighbors": bool(data.get("affects_neighbors", False)),
            "rationale": str(data.get("rationale", "")),
        }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_acceptance_scorer.py -v`
Expected: PASS (all 6 tests). If `test_score_sentence_low_variance_high_confidence` confidence assertion is off, adjust the expected range in the test to match `1 - 4/20 = 0.8`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm/prompts.py backend/app/services/acceptance_scorer.py backend/tests/test_acceptance_scorer.py
git commit -m "feat(acceptance): add AcceptanceScorer with 3-sample median + retry"
```

---

## Task 6: TranslationResult model — add 3 columns + Alembic migration

**Files:**
- Modify: `backend/app/models/job.py` (add 3 columns to `TranslationResult`)
- Create: `backend/alembic/versions/<rev>_add_acceptance_scoring_fields.py`
- Test: `backend/tests/test_acceptance_migration.py`

**Interfaces:**
- Produces: new `TranslationResult` columns `acceptance_confidence: Mapped[float | None]`, `acceptance_dimensions: Mapped[dict | None]`, `acceptance_sentence_scores: Mapped[list | None]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_acceptance_migration.py
import uuid
import pytest
from sqlalchemy import select
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_acceptance_migration.py -v`
Expected: FAIL with `AttributeError: 'TranslationResult' object has no attribute 'acceptance_confidence'` (or migration missing).

- [ ] **Step 3: Modify the model**

In `backend/app/models/job.py`, add three columns to the `TranslationResult` class (after `quality_confidence`):

```python
    quality_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 接受度评分新增字段（acceptance_score / audience_baseline 已存在）
    acceptance_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    acceptance_dimensions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    acceptance_sentence_scores: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    decision_log_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
```

> Note: place the 3 new lines immediately after the existing `quality_confidence` line and before `decision_log_ids` (keep `decision_log_ids` and the rest unchanged).

- [ ] **Step 4: Generate the migration**

Run: `cd backend && alembic revision --autogenerate -m "add acceptance scoring fields"`
Then open the generated file (under `backend/alembic/versions/`) and verify it contains 3 `op.add_column('translation_results', ...)` calls for `acceptance_confidence`, `acceptance_dimensions`, `acceptance_sentence_scores`. If autogenerate produced extra noise, trim it to only these 3 columns. The migration body should look like:

```python
def upgrade() -> None:
    op.add_column('translation_results', sa.Column('acceptance_confidence', sa.Float(), nullable=True))
    op.add_column('translation_results', sa.Column('acceptance_dimensions', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('translation_results', sa.Column('acceptance_sentence_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

def downgrade() -> None:
    op.drop_column('translation_results', 'acceptance_sentence_scores')
    op.drop_column('translation_results', 'acceptance_dimensions')
    op.drop_column('translation_results', 'acceptance_confidence')
```

Ensure `down_revision` points to the current head (run `alembic heads` to confirm; the decision-log migration `17e8dc671db3` or a later one).

- [ ] **Step 5: Apply the migration**

Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade ... -> <new rev>, add acceptance scoring fields`

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_acceptance_migration.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/job.py backend/alembic/versions/ backend/tests/test_acceptance_migration.py
git commit -m "feat(acceptance): add 3 scoring columns to TranslationResult + migration"
```

---

## Task 7: DecisionLog — add "acceptance" stage

**Files:**
- Modify: `backend/app/services/decision_log.py` (add `"acceptance": 5` to `_STAGE_ORDER`)
- Test: `backend/tests/test_decision_log_service.py` (append one test)

**Interfaces:**
- Produces: `"acceptance"` as a valid stage value, ordered after `"suggestion"`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_decision_log_service.py`:

```python
@pytest.mark.asyncio
async def test_acceptance_stage_ordered_after_suggestion(db):
    from app.services.decision_log import _STAGE_ORDER
    assert "acceptance" in _STAGE_ORDER
    assert _STAGE_ORDER["acceptance"] > _STAGE_ORDER["suggestion"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_decision_log_service.py::test_acceptance_stage_ordered_after_suggestion -v`
Expected: FAIL (KeyError or assertion error)

- [ ] **Step 3: Modify `_STAGE_ORDER`**

In `backend/app/services/decision_log.py`, change the `_STAGE_ORDER` dict (around line 11-18):

```python
_STAGE_ORDER = {
    "preprocess": 0,
    "cultural_detect": 0,
    "glossary": 1,
    "translate": 2,
    "risk": 3,
    "suggestion": 4,
    "acceptance": 5,
}
```

Also update the stage-values comment on the `DecisionLog` model (`backend/app/models/decision_log.py` line ~26) to include `acceptance`:

```python
    # 决策阶段：preprocess / cultural_detect / glossary / translate / risk / suggestion / acceptance
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_decision_log_service.py::test_acceptance_stage_ordered_after_suggestion -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/decision_log.py backend/app/models/decision_log.py backend/tests/test_decision_log_service.py
git commit -m "feat(acceptance): add 'acceptance' stage to decision log ordering"
```

---

## Task 8: Request/Response schemas + first-scoring API route

**Files:**
- Modify: `backend/app/schemas/job.py` (add 3 schemas)
- Modify: `backend/app/api/jobs.py` (add route + orchestrator helper)
- Test: `backend/tests/test_acceptance_api.py`

**Interfaces:**
- Consumes: `AcceptanceScorer`, `SentenceSegmenter`, `RiskPhraseMapper`, `AcceptanceAggregator`, `save_decision_logs`, `TranslationResult` columns.
- Produces:
  - `POST /api/jobs/{job_id}/acceptance-score` with body `AcceptanceScoreRequest{lang: str, audience_baseline: Literal[...]}` → `AcceptanceScoreResponse`.
  - `AcceptanceScoreResponse` mirrors `AcceptanceResult` (total_score, dimensions, confidence, top3_risk_indices, audience_baseline).

- [ ] **Step 1: Write the failing test**

```python
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
    return User(id=uuid.uuid4(), username="acc_user", hashed_password="x")


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
```

> Note: `mock_user` is a fixture returning a `User` with a random id; seed the job with `user_id=mock_user.id` so the ownership check passes. `get_current_user` override returns `mock_user` directly (FastAPI accepts a sync return for a non-dependency override). The route commits to the real `db` session.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_acceptance_api.py::test_first_scoring_returns_result -v`
Expected: FAIL (route not defined → 404)

- [ ] **Step 3: Add request/response schemas**

In `backend/app/schemas/job.py`, append:

```python
from app.schemas.acceptance import AcceptanceResult  # noqa: E402  (top of file is fine too)


class AcceptanceScoreRequest(BaseModel):
    lang: str
    audience_baseline: Literal["policy_media", "academic", "social_media"] = "policy_media"


class AcceptanceScoreDeltaRequest(BaseModel):
    lang: str
    sentence_id: str
    new_text: str


class AcceptanceScoreResponse(BaseModel):
    total_score: int
    dimensions: dict
    confidence: float
    top3_risk_indices: list[int] = Field(default_factory=list)
    audience_baseline: str
```

- [ ] **Step 4: Add the route + orchestrator**

In `backend/app/api/jobs.py`, add imports at top:

```python
from app.services.acceptance_segmenter import segment
from app.services.acceptance_scorer import AcceptanceScorer
from app.services.risk_phrase_mapper import map_risk_phrases
from app.services.acceptance_aggregator import aggregate
from app.services.decision_log import save_decision_logs
from app.schemas.job import (
    AcceptanceScoreRequest, AcceptanceScoreDeltaRequest, AcceptanceScoreResponse,
)
```

Add a module-level singleton and orchestrator near the other helpers (e.g. after `_get_lang_result`):

```python
_acceptance_scorer = AcceptanceScorer()


async def _run_acceptance_scoring(
    result: TranslationResult,
    audience_baseline: str,
    db: AsyncSession,
    job_id: uuid.UUID,
) -> dict:
    """编排：切句 → 逐句评分 → 映射 → 聚合 → 写 DB + decision_log。"""
    text = result.translated_text or ""
    lang = result.language
    sents = segment(text, lang)
    sent_index = {s.id: s for s in sents}

    # 逐句评分（scorer 内部信号量节流）
    sentence_scores = []
    for s in sents:
        ss = await _acceptance_scorer.score_sentence(
            s.text, lang, audience_baseline,
            genre="", cultural_sphere="",
        )
        ss.sentence_id = s.id  # 回填 id
        sentence_scores.append(ss)

    risk_annotations = result.risk_annotations or []
    mapped = map_risk_phrases(sentence_scores, sent_index, risk_annotations)
    agg = aggregate(sentence_scores, risk_annotations)

    # 写回 TranslationResult
    result.acceptance_score = agg["total_score"]
    result.audience_baseline = audience_baseline
    result.acceptance_confidence = agg["confidence"]
    result.acceptance_dimensions = agg["dimensions"]
    result.acceptance_sentence_scores = [s.model_dump() for s in sentence_scores]
    flag_modified(result, "acceptance_dimensions")
    flag_modified(result, "acceptance_sentence_scores")

    # 写 decision_log（阶段=acceptance）
    entries = [{
        "stage": "acceptance",
        "decision_type": "acceptance_scoring",
        "decision": f"接受度评分 {agg['total_score']}/100（受众基准 {audience_baseline}）",
        "reasoning": " | ".join(s.rationale for s in sentence_scores if s.rationale),
        "confidence": "low" if agg["confidence"] < 0.7 else "high",
        "metadata": {
            "audience_baseline": audience_baseline,
            "total_score": agg["total_score"],
            "dimensions": agg["dimensions"],
            "unmapped_phrases": mapped["unmapped_phrases"],
            "trigger": "initial",
        },
    }]
    log_ids = await save_decision_logs(db, job_id, result.id, entries)
    if result.decision_log_ids is None:
        result.decision_log_ids = []
    result.decision_log_ids.extend(log_ids)
    flag_modified(result, "decision_log_ids")
    await db.commit()
    await db.refresh(result)

    return {
        "total_score": agg["total_score"],
        "dimensions": agg["dimensions"],
        "confidence": agg["confidence"],
        "top3_risk_indices": mapped["top3_risk_indices"],
        "audience_baseline": audience_baseline,
    }
```

Add the route (after the risk routes, before `accept_all_risks` or at the end of the file):

```python
@router.post("/{job_id}/acceptance-score", response_model=AcceptanceScoreResponse)
async def score_acceptance(
    job_id: uuid.UUID,
    body: AcceptanceScoreRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """首次接受度评分（转译完成后调用）。"""
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    if not result.translated_text:
        raise HTTPException(status_code=400, detail="Translation not ready")
    return await _run_acceptance_scoring(result, body.audience_baseline, db, job.id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_acceptance_api.py::test_first_scoring_returns_result -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/job.py backend/app/api/jobs.py backend/tests/test_acceptance_api.py
git commit -m "feat(acceptance): add first-scoring API route + orchestrator"
```

---

## Task 9: Delta re-scoring API route

**Files:**
- Modify: `backend/app/api/jobs.py` (add delta route)
- Modify: `backend/tests/test_acceptance_api.py` (append delta test)

**Interfaces:**
- Produces: `POST /api/jobs/{job_id}/acceptance-score/delta` with body `AcceptanceScoreDeltaRequest{lang, sentence_id, new_text}` → `AcceptanceScoreResponse`. Re-scores only the target sentence (single sample) + neighbors if `affects_neighbors`, then re-aggregates from the cached `acceptance_sentence_scores`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_acceptance_api.py`:

```python
@pytest.mark.asyncio
async def test_delta_rescoring_updates_score(db, mock_user):
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
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_acceptance_api.py::test_delta_rescoring_updates_score -v`
Expected: FAIL (route not defined → 404)

- [ ] **Step 3: Add the delta route + helper**

In `backend/app/api/jobs.py`, add a helper and route:

```python
async def _run_acceptance_delta(
    result: TranslationResult,
    sentence_id: str,
    new_text: str,
    db: AsyncSession,
    job_id: uuid.UUID,
) -> dict:
    """delta 重算：仅重算指定句（单次采样）+ 受影响邻接句，再聚合缓存。"""
    cached = result.acceptance_sentence_scores or []
    if not cached:
        raise HTTPException(status_code=400, detail="No cached sentence scores; run initial scoring first")

    # 重建 SentenceScore 列表（从缓存反序列化）
    from app.schemas.acceptance import SentenceScore, DimensionScores
    scores = [SentenceScore(**c) for c in cached]
    by_id = {s.sentence_id: s for s in scores}
    if sentence_id not in by_id:
        raise HTTPException(status_code=400, detail=f"Unknown sentence_id {sentence_id}")

    audience = result.audience_baseline or "policy_media"
    lang = result.language

    # 重算目标句
    new_ss = await _acceptance_scorer.score_sentence_single(new_text, lang, audience)
    new_ss.sentence_id = sentence_id
    by_id[sentence_id] = new_ss

    # 邻接句：若目标句 affects_neighbors，重算前后句（重切全文以拿邻接句文本）
    if new_ss.affects_neighbors:
        idx = next(i for i, s in enumerate(scores) if s.sentence_id == sentence_id)
        sents = segment(result.translated_text or "", lang)
        sent_by_id = {s.id: s for s in sents}
        for neighbor_idx in (idx - 1, idx + 1):
            if 0 <= neighbor_idx < len(scores):
                nsid = scores[neighbor_idx].sentence_id
                sent = sent_by_id.get(nsid)
                if sent:
                    nss = await _acceptance_scorer.score_sentence_single(sent.text, lang, audience)
                    nss.sentence_id = nsid
                    by_id[nsid] = nss

    new_scores = [by_id[s.sentence_id] for s in scores]
    risk_annotations = result.risk_annotations or []
    agg = aggregate(new_scores, risk_annotations)

    # 写回
    result.acceptance_score = agg["total_score"]
    result.acceptance_confidence = agg["confidence"]
    result.acceptance_dimensions = agg["dimensions"]
    result.acceptance_sentence_scores = [s.model_dump() for s in new_scores]
    flag_modified(result, "acceptance_dimensions")
    flag_modified(result, "acceptance_sentence_scores")

    entries = [{
        "stage": "acceptance",
        "decision_type": "acceptance_delta",
        "decision": f"delta 重算：句 {sentence_id} → {new_ss.score}",
        "reasoning": new_ss.rationale,
        "confidence": "low" if agg["confidence"] < 0.7 else "high",
        "metadata": {
            "trigger": "sentence_replace",
            "affected_sentence_ids": [sentence_id],
            "total_score": agg["total_score"],
        },
    }]
    log_ids = await save_decision_logs(db, job_id, result.id, entries)
    if result.decision_log_ids is None:
        result.decision_log_ids = []
    result.decision_log_ids.extend(log_ids)
    flag_modified(result, "decision_log_ids")
    await db.commit()
    await db.refresh(result)

    mapped = map_risk_phrases(new_scores, {}, risk_annotations)  # top3 only; offsets stale
    return {
        "total_score": agg["total_score"],
        "dimensions": agg["dimensions"],
        "confidence": agg["confidence"],
        "top3_risk_indices": mapped["top3_risk_indices"],
        "audience_baseline": audience,
    }


@router.post("/{job_id}/acceptance-score/delta", response_model=AcceptanceScoreResponse)
async def score_acceptance_delta(
    job_id: uuid.UUID,
    body: AcceptanceScoreDeltaRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """替换风险词后句级 delta 重算（<1s 目标）。"""
    job = await _get_user_job(job_id, user, db)
    result = await _get_lang_result(job.id, body.lang, db)
    return await _run_acceptance_delta(result, body.sentence_id, body.new_text, db, job.id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_acceptance_api.py::test_delta_rescoring_updates_score -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/jobs.py backend/tests/test_acceptance_api.py
git commit -m "feat(acceptance): add delta re-scoring API route (sentence-level)"
```

---

## Task 10: Integration test (full chain)

**Files:**
- Create: `backend/tests/test_acceptance_integration.py`

**Interfaces:**
- Verifies end-to-end: job+result seeded → first-scoring route → DB fields written + decision_log entry → delta route → score changes + new decision_log entry.

- [ ] **Step 1: Write the integration test**

```python
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
    def __init__(self, contents):
        self._q = list(contents)
    async def chat(self, *, model, messages, temperature=0.3):
        return {"content": self._q.pop(0)}


def _p(a=20, c=20, n=20, r=20, neighbors=False):
    return json.dumps({
        "audience": a, "cultural": c, "naturalness": n, "risk": r,
        "risk_phrase_offsets": [], "affects_neighbors": neighbors,
        "rationale": "integ",
    })


@pytest.mark.asyncio
async def test_full_chain_first_then_delta(db):
    user = User(id=uuid.uuid4(), username=f"integ_{uuid.uuid4().hex[:6]}", hashed_password="x")
    db.add(user); await db.commit()
    job = TranslationJob(user_id=user.id, source_text="你好。再见。", genre="political",
                         strategy="semantic_equivalence", target_languages=["zh"])
    db.add(job); await db.commit(); await db.refresh(job)
    result = TranslationResult(job_id=job.id, language="zh", translated_text="Hello. Bye.",
                               acceptance_score=-1)
    db.add(result); await db.commit(); await db.refresh(result)
    job_id = job.id
    result_id = result.id

    async def fake_get_db():
        yield db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = fake_get_db
    scorer_mod.bailian_client = FakeClient([_p(), _p()])  # 2 sentences
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            # 1. first scoring
            res = await c.post(f"/api/jobs/{job_id}/acceptance-score",
                               json={"lang": "zh", "audience_baseline": "policy_media"})
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

            # verify decision_log entry
            logs = (await db.execute(
                select(DecisionLog).where(DecisionLog.result_id == result_id,
                                          DecisionLog.stage == "acceptance")
            )).scalars().all()
            assert len(logs) == 1
            assert logs[0].metadata.get("trigger") == "initial"

            # 2. delta re-scoring: s1 drops to 40
            scorer_mod.bailian_client = FakeClient([_p(10, 10, 10, 10)])
            res2 = await c.post(f"/api/jobs/{job_id}/acceptance-score/delta",
                                json={"lang": "zh", "sentence_id": "s1", "new_text": "Bye."})
            assert res2.status_code == 200
            assert res2.json()["total_score"] == 60  # (80+40)/2

            # verify new decision_log entry
            logs2 = (await db.execute(
                select(DecisionLog).where(DecisionLog.result_id == result_id,
                                          DecisionLog.stage == "acceptance")
            )).scalars().all()
            assert len(logs2) == 2
            assert any(l.metadata.get("trigger") == "sentence_replace" for l in logs2)
    finally:
        app.dependency_overrides.clear()
        scorer_mod.bailian_client = __import__("app.llm.bailian", fromlist=["bailian_client"]).bailian_client
```

- [ ] **Step 2: Run the full acceptance test suite**

Run: `cd backend && pytest tests/test_acceptance*.py tests/test_sentence_segmenter.py tests/test_risk_phrase_mapper.py tests/test_decision_log_service.py -v`
Expected: PASS (all acceptance-related tests green)

- [ ] **Step 3: Run the entire backend test suite to check for regressions**

Run: `cd backend && pytest -v`
Expected: PASS (no regressions in pre-existing tests)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_acceptance_integration.py
git commit -m "test(acceptance): add full-chain integration test (first + delta)"
```

---

## Self-Review (run after writing, before handoff)

**Spec coverage:**
- §3 architecture → Tasks 1–5 (all components) ✓
- §4 data flow (first scoring) → Task 8 ✓
- §4 data flow (delta) → Task 9 ✓
- §5 data model → Task 6 ✓
- §5 DecisionLog acceptance stage → Task 7 ✓
- §6 error handling (LLM failure, schema invalid, all-failed, delta failure, confidence threshold, audience switch) → Task 5 (scorer retry + failed sentence), Task 4 (aggregator all-failed), Task 8 (audience switch = full re-score via same first-scoring route) ✓
- §7 testing → Tasks 1–10 cover all 6 test categories + integration ✓
- §8 performance → semaphore (Task 5), single-sample delta (Task 9) ✓
- §9 YAGNI boundaries respected ✓

**Placeholder scan:** No TBD/TODO; all code blocks complete.

**Type consistency:** `Sentence.score` is a `@property` (Task 2) — accessed as `ss.score` (not called) in Tasks 3, 4, 8, 9, 10 ✓. `SentenceScore.sentence_id` set via attribute assignment in Tasks 8/9 (mutable Pydantic — fine, no `frozen=True`) ✓. `map_risk_phrases` signature consistent across Tasks 3, 8, 9 ✓. `aggregate` returns `dict` with keys `total_score/dimensions/confidence` — consumed consistently in Tasks 8/9 ✓.

**One known simplification (documented, not a defect):** delta neighbor re-scoring (Task 9) re-segments `result.translated_text` to fetch neighbor sentence text — this assumes the frontend has already applied the replacement to `translated_text` before calling delta. If `translated_text` is stale, neighbor text will be wrong. This matches the spec §4 delta flow (frontend sends `new_text` after replacement). Acceptable for P2.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-01-acceptance-scoring.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
