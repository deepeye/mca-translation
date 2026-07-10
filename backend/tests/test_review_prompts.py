"""Tests for review prompt language requirements.

Ensure DUAL_REVIEW_PROMPT and SINGLE_REVIEW_PROMPT instruct the LLM to
write suggestion / original / span.text fields in the target language only,
without any Chinese characters, pinyin, or mixed-script text.
"""


def test_dual_review_prompt_requires_target_language_suggestion():
    from app.llm.prompts import DUAL_REVIEW_PROMPT

    prompt = DUAL_REVIEW_PROMPT.format(
        source_text="坚决克服麻痹思想和侥幸心理",
        translated_text="resolutely overcome complacency and lucky psychology",
        target_language="English",
        audience="general_public",
        cultural_sphere="western_english",
    )
    assert "suggestion 必须是" in prompt or "suggestion：修改建议（必须使用" in prompt
    assert "不得包含任何中文" in prompt


def test_single_review_prompt_requires_target_language_suggestion():
    from app.llm.prompts import SINGLE_REVIEW_PROMPT

    prompt = SINGLE_REVIEW_PROMPT.format(
        translated_text="resolutely overcome complacency and lucky psychology",
        target_language="English",
        audience="general_public",
        cultural_sphere="western_english",
    )
    assert "suggestion 必须是" in prompt or "suggestion：修改建议（必须使用" in prompt
    assert "不得包含任何中文" in prompt
