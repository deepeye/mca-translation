"""Test that translate() collects decision_entries from pipeline stages."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.translation import TranslationPipeline


@pytest.mark.asyncio
async def test_translate_returns_decision_entries_with_risk():
    """translate() should include risk_identified entries from risk annotation."""
    pipeline = TranslationPipeline()

    # Mock cultural_preprocess to return None (no cultural sphere)
    # Mock _main_translation to return a fixed translation
    # Mock _risk_annotation to return one risk
    with patch.object(pipeline, "_main_translation", AsyncMock(return_value="translated text")), \
         patch.object(pipeline, "_risk_annotation", AsyncMock(return_value=[
             {"phrase": "bad phrase", "risk_level": "high",
              "risk_type": "cognitive_bias", "explanation": "可能引起误解",
              "offset": 0, "status": "open"}
         ])):
        output = await pipeline.translate(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
        )

    assert "decision_entries" in output
    risk_entries = [e for e in output["decision_entries"] if e["stage"] == "risk"]
    assert len(risk_entries) == 1
    assert risk_entries[0]["decision_type"] == "risk_identified"
    assert risk_entries[0]["confidence"] == "high"
    assert risk_entries[0]["target_phrase"] == "bad phrase"


@pytest.mark.asyncio
async def test_translate_no_risk_returns_empty_decision_entries():
    """translate() with no risks should return empty decision_entries."""
    pipeline = TranslationPipeline()
    with patch.object(pipeline, "_main_translation", AsyncMock(return_value="translated text")), \
         patch.object(pipeline, "_risk_annotation", AsyncMock(return_value=[])):
        output = await pipeline.translate(
            source_text="原文",
            genre="news",
            strategy="semantic_equivalence",
            target_language="en-GB",
        )
    assert output["decision_entries"] == []
