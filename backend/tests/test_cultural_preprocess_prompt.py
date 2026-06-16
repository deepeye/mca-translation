"""验证 CULTURAL_PREPROCESS_PROMPT 注入文化圈/受众/文体后的结果。"""
from app.llm.cultural_profiles import (
    AUDIENCE_TYPE_GUIDELINES,
    CULTURAL_SPHERE_PROFILES,
)
from app.llm.prompts import CULTURAL_PREPROCESS_PROMPT


def test_prompt_contains_required_placeholders():
    for placeholder in (
        "{source_text}",
        "{cultural_sphere_profile}",
        "{audience_type_guideline}",
        "{genre}",
    ):
        assert placeholder in CULTURAL_PREPROCESS_PROMPT, placeholder


def test_prompt_renders_with_known_values():
    rendered = CULTURAL_PREPROCESS_PROMPT.format(
        source_text="共同富裕不是平均主义。",
        cultural_sphere_profile=CULTURAL_SPHERE_PROFILES["western_english"],
        audience_type_guideline=AUDIENCE_TYPE_GUIDELINES["general_public"],
        genre="political",
    )
    assert "共同富裕不是平均主义。" in rendered
    assert "欧美英语圈" in rendered
    assert "公众读者" in rendered
    assert "political" in rendered
    # JSON 输出说明
    assert "culture_loaded_terms" in rendered
    assert "cultural_notes" in rendered
    assert "taboo_warnings" in rendered
