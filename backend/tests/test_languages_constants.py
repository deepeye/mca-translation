"""验证目标语言常量表与 descriptor 函数。"""
from app.constants.languages import (
    SUPPORTED_LANGUAGES,
    SUPPORTED_LANGUAGE_CODES,
    get_language,
    is_supported_language,
    language_descriptor,
)


def test_supports_18_languages_including_new_13():
    codes = {lang.code for lang in SUPPORTED_LANGUAGES}
    assert len(codes) == 18
    for code in ["ru-RU", "ar", "ko-KR", "pt-BR", "sw-KE", "it-IT", "kk-KZ",
                 "th-TH", "ms-MY", "el-GR", "vi-VN", "ur-PK", "hi-IN"]:
        assert code in codes, f"missing {code}"
    for code in ["en-GB", "de-DE", "ja-JP", "es-ES", "fr-FR"]:
        assert code in codes


def test_is_supported_language_true_false():
    assert is_supported_language("en-GB") is True
    assert is_supported_language("ar") is True
    assert is_supported_language("xx-XX") is False
    assert is_supported_language("") is False


def test_descriptor_ltr_latin_returns_name_only():
    assert language_descriptor("en-GB") == "English"
    assert language_descriptor("sw-KE") == "Swahili"
    assert language_descriptor("pt-BR") == "Portuguese"


def test_descriptor_rtl_includes_script_and_direction():
    assert language_descriptor("ar") == "Arabic (Arabic script, right-to-left)"
    assert language_descriptor("ur-PK") == "Urdu (Arabic script, right-to-left)"


def test_descriptor_non_latin_ltr_includes_script_only():
    assert language_descriptor("kk-KZ") == "Kazakh (Cyrillic script)"
    assert language_descriptor("hi-IN") == "Hindi (Devanagari script)"
    assert language_descriptor("ja-JP") == "Japanese (Japanese script)"


def test_descriptor_unknown_code_falls_back_to_raw():
    assert language_descriptor("xx-XX") == "xx-XX"


def test_affinity_mapping_for_key_languages():
    assert get_language("ru-RU").affinity_sphere == "russian_sphere"
    assert get_language("ar").affinity_sphere == "islamic_middle_east"
    assert get_language("pt-BR").affinity_sphere == "latin_american"
    assert get_language("hi-IN").affinity_sphere == "south_asian"
    assert get_language("th-TH").affinity_sphere is None
    assert get_language("ms-MY").affinity_sphere is None


def test_rtl_languages_are_exactly_arabic_and_urdu():
    rtl = {lang.code for lang in SUPPORTED_LANGUAGES if lang.direction == "rtl"}
    assert rtl == {"ar", "ur-PK"}
