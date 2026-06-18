import pytest
from app.services.translation import build_translation_system_prompt
from app.schemas.job import CulturalPreprocessResult


def test_build_translation_system_prompt_without_glossary():
    """When source_text is not provided, no glossary block should appear."""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="semantic_equivalence",
    )
    assert "<glossary_terms>" not in prompt


def test_build_translation_system_prompt_with_glossary():
    """When source_text contains known terms, glossary block should be injected."""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="semantic_equivalence",
        source_text="我们推进五位一体总体布局",
    )
    assert "<glossary_terms>" in prompt
    assert "五位一体" in prompt
    assert "Five-sphere Overall Plan" in prompt


def test_build_translation_system_prompt_filters_genre():
    """Terms not matching genre should be filtered out."""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="brand",
        strategy="semantic_equivalence",
        source_text="撸起袖子加油干",
    )
    assert "<glossary_terms>" not in prompt
