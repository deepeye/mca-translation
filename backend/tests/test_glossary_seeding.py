"""验证术语 seeding 脚本与合并加载。"""
import asyncio
import json

from app.services.hardcoded_glossary import (
    _HARDCODED_TERMS,
    apply_generated_translations,
    get_term_translation,
)


def _term(source_term):
    return next(t for t in _HARDCODED_TERMS if t.source_term == source_term)


def test_apply_generated_translations_merges_new_language():
    original = {t.source_term: dict(t.translations) for t in _HARDCODED_TERMS}
    try:
        gen = {"五位一体": {"ru-RU": {"rendering": "Пять сфер", "alternatives": [], "notes": "x"}}}
        apply_generated_translations(gen)
        info = get_term_translation(_term("五位一体"), "ru-RU")
        assert info["preferred"] == "Пять сфер"
    finally:
        for t in _HARDCODED_TERMS:
            t.translations = original[t.source_term]


def test_apply_generated_translations_handcurated_wins():
    original = {t.source_term: dict(t.translations) for t in _HARDCODED_TERMS}
    try:
        gen = {"五位一体": {"en-GB": {"rendering": "WRONG", "alternatives": [], "notes": ""}}}
        apply_generated_translations(gen)
        info = get_term_translation(_term("五位一体"), "en-GB")
        assert info["preferred"] == "Five-sphere Overall Plan"
    finally:
        for t in _HARDCODED_TERMS:
            t.translations = original[t.source_term]


class _MockClient:
    def __init__(self, payload):
        self._payload = payload

    async def chat(self, **kwargs):
        return {"content": json.dumps(self._payload)}


def test_generate_for_language_returns_valid_structure():
    from app.generate_glossary_translations import _generate_for_language
    payload = {
        "五位一体": {"rendering": "Пять сфер", "alternatives": ["альт"], "notes": "прим"},
        "一带一路": {"rendering": "Один пояс, один путь", "alternatives": [], "notes": ""},
        "unknown_term": {"rendering": "x", "alternatives": [], "notes": ""},
    }
    out = asyncio.run(_generate_for_language(_MockClient(payload), "ru-RU"))
    assert out["五位一体"]["rendering"] == "Пять сфер"
    assert "unknown_term" not in out  # 非真实术语被过滤


def test_load_generated_translations_returns_empty_dict_for_null_translations(tmp_path, monkeypatch):
    """当 JSON 文件包含 {"translations": null} 时，_load_generated_translations 应返回 {} 而不是 None 或崩溃。"""
    from app.services import hardcoded_glossary
    fake_file = tmp_path / "glossary_translations_generated.json"
    fake_file.write_text(json.dumps({"translations": None}), encoding="utf-8")
    monkeypatch.setattr(hardcoded_glossary, "_GENERATED_FILE", fake_file)
    result = hardcoded_glossary._load_generated_translations()
    assert result == {}
    assert isinstance(result, dict)
