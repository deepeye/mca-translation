"""验证文化圈和受众类型常量表的完整性。"""
from app.llm.cultural_profiles import (
    AUDIENCE_TYPE_GUIDELINES,
    CULTURAL_SPHERE_PROFILES,
    SUPPORTED_AUDIENCE_TYPES,
    SUPPORTED_CULTURAL_SPHERES,
)


def test_cultural_sphere_profiles_cover_all_keys():
    expected = {
        "western_english",
        "european_continental",
        "islamic_middle_east",
        "east_asian_confucian",
        "latin_american",
        "russian_sphere",
        "south_asian",
        "african",
    }
    assert set(CULTURAL_SPHERE_PROFILES.keys()) == expected
    assert set(SUPPORTED_CULTURAL_SPHERES) == expected
    for key, value in CULTURAL_SPHERE_PROFILES.items():
        assert isinstance(value, str) and len(value.strip()) >= 30, key


def test_audience_type_guidelines_cover_all_keys():
    expected = {
        "general_public",
        "media",
        "government",
        "academic",
        "business",
        "diaspora_chinese",
    }
    assert set(AUDIENCE_TYPE_GUIDELINES.keys()) == expected
    assert set(SUPPORTED_AUDIENCE_TYPES) == expected
    for key, value in AUDIENCE_TYPE_GUIDELINES.items():
        assert isinstance(value, str) and len(value.strip()) >= 20, key


def test_western_english_profile_avoids_over_adaptive_language():
    """欧美英语圈画像不应包含可能诱导模型过度特指翻译的强指令词汇。"""
    profile = CULTURAL_SPHERE_PROFILES["western_english"]
    assert "天然警惕" not in profile
    assert "通常需要更多具体语境才能接受" in profile
