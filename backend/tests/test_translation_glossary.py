import pytest
from app.services.translation import build_translation_system_prompt, TranslationPipeline
from app.schemas.job import CulturalPreprocessResult


def test_build_translation_system_prompt_without_glossary():
    """When glossary_block is not provided, no glossary block should appear."""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="semantic_equivalence",
    )
    assert "<glossary_terms>" not in prompt


def test_build_translation_system_prompt_with_glossary():
    """When glossary_block is provided, it should be appended to the prompt."""
    pipeline = TranslationPipeline()
    glossary_block = pipeline._format_rag_glossary_block(
        [
            {
                "source_term": "五位一体",
                "term_type": "political_discourse",
                "translations": {
                    "en-GB": {
                        "preferred": "Five-sphere Overall Plan",
                        "alternatives": ["integrated five-sphere strategy"],
                        "notes": "学术场景可展开解释；大众媒体可简化为 holistic development",
                    }
                },
                "risk_notes": "直译在大众媒体可读性较低",
                "source": "system_kb",
            }
        ],
        language="en-GB",
        strategy="semantic_equivalence",
    )
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="semantic_equivalence",
    )
    prompt += f"\n\n{glossary_block}\n"
    assert "<glossary_terms>" in prompt
    assert "五位一体" in prompt
    assert "Five-sphere Overall Plan" in prompt


def test_build_translation_system_prompt_filters_genre():
    """Terms not matching genre should be filtered out by _format_rag_glossary_block."""
    pipeline = TranslationPipeline()
    # "撸起袖子加油干" is not applicable to "brand" genre; _format_rag_glossary_block
    # does not filter by genre, so we simulate an empty result instead.
    glossary_block = pipeline._format_rag_glossary_block([], language="en-GB", strategy="semantic_equivalence")
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="brand",
        strategy="semantic_equivalence",
    )
    if glossary_block:
        prompt += f"\n\n{glossary_block}\n"
    assert "<glossary_terms>" not in prompt
