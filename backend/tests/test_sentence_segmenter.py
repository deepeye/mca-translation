# backend/tests/test_sentence_segmenter.py
from app.services.acceptance_segmenter import segment, Sentence


def test_segment_english_period():
    sents = segment("Hello world. Goodbye moon.", "en")
    assert [s.text for s in sents] == ["Hello world.", "Goodbye moon."]
    assert sents[0].id == "s0"
    assert sents[0].char_offset == 0
    assert sents[1].char_offset == 13  # len("Hello world. ")
    assert sents[1].id == "s1"


def test_segment_chinese_full_stop():
    sents = segment("你好世界。再见月亮。", "zh")
    assert [s.text for s in sents] == ["你好世界。", "再见月亮。"]
    assert sents[1].char_offset == 5


def test_segment_japanese():
    sents = segment("こんにちは。さようなら。", "ja")
    assert len(sents) == 2
    assert sents[0].text == "こんにちは。"


def test_segment_single_sentence_no_terminator():
    sents = segment("Just one sentence without terminator", "en")
    assert len(sents) == 1
    assert sents[0].text == "Just one sentence without terminator"
    assert sents[0].char_offset == 0


def test_segment_empty_text():
    assert segment("", "en") == []


def test_segment_preserves_abbreviations_dr():
    # Dr. should not split
    sents = segment("Dr. Smith arrived. He left.", "en")
    assert [s.text for s in sents] == ["Dr. Smith arrived.", "He left."]


def test_segment_consecutive_punctuation():
    sents = segment("What?! Yes.", "en")
    # "What?!" is one sentence
    assert [s.text for s in sents] == ["What?!", "Yes."]