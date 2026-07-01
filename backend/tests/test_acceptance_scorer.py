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


@pytest.mark.asyncio
async def test_score_sentence_malformed_offsets_does_not_crash():
    # 回归保护：畸形 risk_phrase_offsets 条目不应让整个样本失效。
    # 该样本仍应贡献有效 dimensions（仅 offsets 降级为空）。
    malformed = json.dumps({
        "audience": 20, "cultural": 20, "naturalness": 20, "risk": 20,
        "risk_phrase_offsets": [["bad"], [5], "5-10", {"x": 1}, [1, 2, 3]],
        "affects_neighbors": False,
        "rationale": "ok",
    })
    client = FakeClient([malformed, _payload((20, 20, 20, 20)), _payload((20, 20, 20, 20))])
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence("Hello.", "en", "policy_media")
    # 3 个样本均有效（malformed 样本 offsets 降级为空但 dimensions 保留）
    assert ss.failed is False
    assert ss.score == 80


@pytest.mark.asyncio
async def test_score_sentence_affects_neighbors_string_false_not_inverted():
    # 回归保护：LLM 返回字符串 "false" 时不应被反转为 True。
    payload = json.dumps({
        "audience": 20, "cultural": 20, "naturalness": 20, "risk": 20,
        "risk_phrase_offsets": [],
        "affects_neighbors": "false",
        "rationale": "ok",
    })
    client = FakeClient([payload, payload, payload])
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence("Hello.", "en", "policy_media")
    assert ss.affects_neighbors is False


class _ExceptionThenValidClient:
    """首次 chat 抛异常，第二次起返回固定 payload。守护 I3：LLM 异常也重试。"""
    def __init__(self, valid_content: str):
        self._valid = valid_content
        self.calls = 0

    async def chat(self, *, model, messages, temperature=0.3):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("LLM down")
        return {"content": self._valid}


@pytest.mark.asyncio
async def test_score_sentence_retries_on_llm_exception():
    # I3 守护：首次 LLM 调用抛异常 → 重试 1 次 → 成功。score_sentence_single 单采样路径。
    client = _ExceptionThenValidClient(_payload((20, 20, 20, 20)))
    scorer = AcceptanceScorer(llm_client=client)
    ss = await scorer.score_sentence_single("Hello.", "en", "policy_media")
    assert ss.failed is False
    assert ss.score == 80
    assert client.calls == 2  # 首次异常 + 重试成功
