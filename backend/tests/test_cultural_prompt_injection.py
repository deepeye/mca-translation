"""验证主翻译 system prompt 在有/无 cultural_constraints 时的差异。"""
from app.schemas.job import (
    CulturalLoadedTerm,
    CulturalPreprocessResult,
)
from app.services.translation import build_translation_system_prompt


def _make_result() -> CulturalPreprocessResult:
    return CulturalPreprocessResult(
        culture_loaded_terms=[
            CulturalLoadedTerm(
                term="共同富裕",
                culture_gap="high",
                adaptation_strategy="explanatory",
                suggested_rendering="a policy initiative for balanced wealth distribution",
                reason="lacks Western context",
            ),
            CulturalLoadedTerm(
                term="新质生产力",
                culture_gap="medium",
                adaptation_strategy="explanatory",
                suggested_rendering="innovation-driven productive forces",
                reason="abstract policy term",
            ),
            CulturalLoadedTerm(
                term="熊猫",
                culture_gap="low",
                adaptation_strategy="literal",
                suggested_rendering="panda",
                reason="universally known",
            ),
        ],
        cultural_notes=["避免国家主导叙事框架"],
        taboo_warnings=["避免宗教治理表述"],
    )


def test_prompt_without_cultural_constraints_omits_section():
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="audience_first",
        cultural_constraints=None,
        cultural_sphere=None,
        audience_type=None,
    )
    assert "<cultural_constraints>" not in prompt
    assert "English" in prompt
    assert "political" in prompt


def test_prompt_with_cultural_constraints_includes_section():
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="audience_first",
        cultural_constraints=_make_result(),
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert "<cultural_constraints>" in prompt
    assert "</cultural_constraints>" in prompt
    # 高文化差异 -> MUST_USE
    assert "MUST_USE" in prompt and "共同富裕" in prompt
    # 中文化差异 -> SUGGEST
    assert "SUGGEST" in prompt and "新质生产力" in prompt
    # 低文化差异 -> 不生成约束（不出现 LITERAL 这种关键字）
    assert "熊猫" not in prompt or prompt.count("熊猫") == 0
    # 文化注意事项 + 禁忌
    assert "避免国家主导叙事框架" in prompt
    assert "避免宗教治理表述" in prompt
    # 文化圈 / 受众也注入
    assert "欧美英语圈" in prompt
    assert "公众读者" in prompt


def test_prompt_with_empty_constraints_still_includes_section():
    """没有文化负载词，但仍传入 cultural_sphere/audience_type 时仍应注入特征段。"""
    empty = CulturalPreprocessResult()
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="audience_first",
        cultural_constraints=empty,
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert "<cultural_constraints>" in prompt
    assert "欧美英语圈" in prompt
