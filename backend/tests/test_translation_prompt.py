"""Tests for translation system prompt construction."""
import pytest
from unittest.mock import patch

from app.services.translation import build_translation_system_prompt, TranslationPipeline


def test_prompt_includes_neutral_term_constraint_for_semantic_equivalence():
    """信息等值策略下应注入中性通用词保护约束。"""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="semantic_equivalence",
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert "[翻译策略约束]" in prompt
    assert "当前为信息等值模式" in prompt
    assert "普通政治/国家类通用词汇" in prompt


def test_prompt_excludes_neutral_term_constraint_for_audience_first():
    """受众优先策略下不应注入该约束。"""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="audience_first",
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert "[翻译策略约束]" not in prompt
    assert "当前为信息等值模式" not in prompt


def test_prompt_excludes_constraint_when_no_cultural_sphere():
    """未选择文化圈时自然也不应出现该约束。"""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="semantic_equivalence",
    )
    assert "[翻译策略约束]" not in prompt


@pytest.mark.asyncio
async def test_main_translation_sends_constraint_to_llm_for_semantic_equivalence():
    """验证真正发往 LLM 的 system prompt 包含约束。"""
    pipeline = TranslationPipeline()
    captured = {}

    async def fake_chat_stream(*, model, messages, temperature=0.3):
        captured["messages"] = messages
        yield "The country plays an important role."

    with patch("app.services.translation.bailian_client.chat_stream", fake_chat_stream):
        await pipeline._main_translation(
            source_text="国家发挥着重要作用。",
            genre="political",
            strategy="semantic_equivalence",
            target_language="en-GB",
            cultural_sphere="western_english",
            audience_type="general_public",
        )
    system_prompt = captured["messages"][0]["content"]
    assert "当前为信息等值模式" in system_prompt
    assert "普通政治/国家类通用词汇" in system_prompt


@pytest.mark.asyncio
async def test_main_translation_omits_constraint_for_audience_first():
    """验证受众优先策略下发往 LLM 的 system prompt 不包含约束。"""
    pipeline = TranslationPipeline()
    captured = {}

    async def fake_chat_stream(*, model, messages, temperature=0.3):
        captured["messages"] = messages
        yield "translated text"

    with patch("app.services.translation.bailian_client.chat_stream", fake_chat_stream):
        await pipeline._main_translation(
            source_text="国家发挥着重要作用。",
            genre="political",
            strategy="audience_first",
            target_language="en-GB",
            cultural_sphere="western_english",
            audience_type="general_public",
        )
    system_prompt = captured["messages"][0]["content"]
    assert "当前为信息等值模式" not in system_prompt
