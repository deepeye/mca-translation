"""验证硬编码政治术语词典的查询与格式化行为。"""

from app.services.hardcoded_glossary import (
    find_terms_in_text,
    format_glossary_block,
    get_term_translation,
    _term_by_source,
)


def test_find_terms_in_text():
    text = "我们要坚持以人民为中心的发展思想，统筹推进五位一体总体布局。"
    matched = find_terms_in_text(text)
    sources = {term.source_term for term in matched}
    assert "以人民为中心" in sources
    assert "五位一体" in sources


def test_find_terms_empty():
    matched = find_terms_in_text("今天天气不错，适合出门散步。")
    assert matched == []


def test_find_terms_empty_text():
    assert find_terms_in_text("") == []


def test_format_glossary_block():
    text = "统筹推进五位一体总体布局"
    matched = find_terms_in_text(text)
    block = format_glossary_block(
        matched, language="en-GB", genre="political", strategy="semantic_equivalence"
    )
    assert "<glossary_terms>" in block
    assert "</glossary_terms>" in block
    assert "Five-sphere Overall Plan" in block
    assert block.count("<glossary_terms>") == 1
    assert 'type="political_discourse"' in block


def test_format_glossary_block_filters_genre():
    text = "撸起袖子加油干"
    matched = find_terms_in_text(text)
    block = format_glossary_block(
        matched, language="en-GB", genre="brand", strategy="semantic_equivalence"
    )
    assert block == ""


def test_get_term_translation_audience_first():
    term = _term_by_source["以人民为中心"]
    info = get_term_translation(term, "en-GB", strategy="audience_first")
    # audience_first 取最后一个备选作为简化版本
    assert info["preferred"] == "people-first"
    assert info["alternatives"] == ["people-first"]


def test_get_term_translation_semantic_default():
    term = _term_by_source["以人民为中心"]
    info = get_term_translation(term, "en-GB")
    assert info["preferred"] == "people-centered"


def test_get_term_translation_unknown_language():
    term = _term_by_source["以人民为中心"]
    info = get_term_translation(term, "xx-XX")
    assert info["preferred"] == ""
    assert info["alternatives"] == []


def test_format_glossary_block_no_match_returns_empty():
    matched = find_terms_in_text("普通文本无术语")
    block = format_glossary_block(
        matched, language="en-GB", genre="political", strategy="semantic_equivalence"
    )
    assert block == ""
