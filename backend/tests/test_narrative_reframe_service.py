import json

import pytest

from app.schemas.narrative_reframe import NarrativeReframeAnalysis
from app.services.narrative_reframe import compute_text_hash, parse_analysis_payload, NarrativeReframeService


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def chat(self, *, model, messages, temperature=0.3):
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        return {"content": self.content}


def test_compute_text_hash_is_stable_sha256():
    assert compute_text_hash("Hello") == compute_text_hash("Hello")
    assert compute_text_hash("Hello") != compute_text_hash("Hello!")
    assert len(compute_text_hash("Hello")) == 64


def test_parse_analysis_payload_accepts_json_fenced_block():
    payload = {
        "source_outline": [], "current_translation_outline": [], "recommended_outline": [],
        "overall_rationale": "无需重排", "confidence": 0.7,
    }
    parsed = parse_analysis_payload("```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```")
    assert isinstance(parsed, NarrativeReframeAnalysis)
    assert parsed.overall_rationale == "无需重排"


def test_parse_analysis_payload_rejects_invalid_json():
    with pytest.raises(ValueError, match="Invalid narrative analysis JSON"):
        parse_analysis_payload("not json")


@pytest.mark.asyncio
async def test_analyze_calls_llm_and_returns_schema():
    payload = {
        "source_outline": [{"id": "s1", "order": 1, "summary": "背景", "text_span": "背景"}],
        "current_translation_outline": [{"id": "t1", "order": 1, "summary": "Background", "text_span": "Background"}],
        "recommended_outline": [],
        "overall_rationale": "结构可接受", "confidence": 0.9,
    }
    service = NarrativeReframeService(llm_client=FakeClient(json.dumps(payload, ensure_ascii=False)))
    analysis = await service.analyze(
        source_text="背景", translated_text="Background", genre="news",
        target_language="en", cultural_sphere="western", audience_type="general_public",
    )
    assert analysis.confidence == 0.9


@pytest.mark.asyncio
async def test_preview_returns_llm_text():
    service = NarrativeReframeService(llm_client=FakeClient("Lead first. Background second."))
    analysis = NarrativeReframeAnalysis(source_outline=[], current_translation_outline=[], recommended_outline=[], overall_rationale="ok", confidence=0.8)
    text = await service.preview(translated_text="Background. Lead.", analysis=analysis, target_language="en", mode="light_cohesion")
    assert text == "Lead first. Background second."
