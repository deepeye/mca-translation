from pydantic import ValidationError
from app.schemas.glossary import (
    GlossaryEntryCreate,
    GlossaryEntryUpdate,
    TranslationEntry,
    UserGlossaryEntryCreate,
    UserGlossaryEntryUpdate,
)


def _valid_translations():
    return {"en-GB": TranslationEntry(preferred="x")}


def _invalid_translations():
    return {
        "en-GB": TranslationEntry(preferred="x"),
        "xx-XX": TranslationEntry(preferred="y"),
    }


def test_user_glossary_create_accepts_valid_language_codes():
    body = UserGlossaryEntryCreate(
        source_term="一带一路",
        term_type="user_defined",
        translations=_valid_translations(),
    )
    assert "en-GB" in body.translations


def test_user_glossary_create_rejects_unknown_language_codes():
    try:
        UserGlossaryEntryCreate(
            source_term="一带一路",
            term_type="user_defined",
            translations=_invalid_translations(),
        )
    except ValidationError as e:
        assert "xx-XX" in str(e)
    else:
        raise AssertionError("Expected ValidationError for unknown language code")


def test_user_glossary_update_rejects_unknown_language_codes():
    try:
        UserGlossaryEntryUpdate(translations=_invalid_translations())
    except ValidationError as e:
        assert "xx-XX" in str(e)
    else:
        raise AssertionError("Expected ValidationError for unknown language code")


def test_glossary_create_accepts_valid_language_codes():
    body = GlossaryEntryCreate(
        source_term="一带一路",
        term_type="political_discourse",
        translations=_valid_translations(),
    )
    assert "en-GB" in body.translations


def test_glossary_create_rejects_unknown_language_codes():
    try:
        GlossaryEntryCreate(
            source_term="一带一路",
            term_type="political_discourse",
            translations=_invalid_translations(),
        )
    except ValidationError as e:
        assert "xx-XX" in str(e)
    else:
        raise AssertionError("Expected ValidationError for unknown language code")


def test_glossary_update_rejects_unknown_language_codes():
    try:
        GlossaryEntryUpdate(translations=_invalid_translations())
    except ValidationError as e:
        assert "xx-XX" in str(e)
    else:
        raise AssertionError("Expected ValidationError for unknown language code")
